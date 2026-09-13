"""Vetaura iteration 7 regression tests — code-review bug fixes (undefined vars, empty catches, stale closures, index-as-key)."""
import os
import uuid
import asyncio
import pytest
import requests


def _load_backend_url():
    url = os.environ.get("REACT_APP_BACKEND_URL", "")
    if not url:
        try:
            with open("/app/frontend/.env") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        url = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    return url.rstrip("/")


BASE_URL = _load_backend_url()
API = f"{BASE_URL}/api"

VET1 = "vet1@example.com"
VET2 = "vet2@example.com"
PASS = "strongpass123"
ADMIN_TOKEN = "admin-cron-secret-change-me"


def _login(session, email, password=PASS):
    r = session.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("token") or data.get("access_token")
    assert tok, data
    session.headers["Authorization"] = f"Bearer {tok}"
    return data, tok


@pytest.fixture(scope="module")
def vet1():
    s = requests.Session()
    s.headers["Content-Type"] = "application/json"
    _login(s, VET1)
    return s


@pytest.fixture(scope="module")
def vet2():
    s = requests.Session()
    s.headers["Content-Type"] = "application/json"
    _login(s, VET2)
    return s


@pytest.fixture(scope="module")
def vet1_me(vet1):
    r = vet1.get(f"{API}/auth/me")
    assert r.status_code == 200
    return r.json()


# ---------- Regression: plans ----------
class TestPlans:
    def test_plans_amounts(self):
        r = requests.get(f"{API}/plans")
        assert r.status_code == 200, r.text
        body = r.json()
        plans = body.get("plans") if isinstance(body, dict) else body
        assert isinstance(plans, list) and len(plans) >= 4
        by_key = {p.get("lookup_key"): p for p in plans}
        assert by_key["vetaura_starter_monthly"]["amount"] == 24900
        assert by_key["vetaura_growth_monthly"]["amount"] == 49900
        assert by_key["vetaura_pro_monthly"]["amount"] == 89900
        # scribe add-on lookup key (per iter-5/6 seed)
        scribe_key = "vetaura_scribe_addon_monthly" if "vetaura_scribe_addon_monthly" in by_key else "vetaura_scribe_monthly"
        assert by_key[scribe_key]["amount"] == 7900


# ---------- Regression: login (already covered by fixture, but explicit) ----------
class TestLogin:
    def test_login_returns_jwt(self):
        s = requests.Session()
        _, tok = _login(s, VET1)
        # JWT has 3 dot-separated segments
        assert isinstance(tok, str) and tok.count(".") == 2


# ---------- Regression: Stripe checkout (session None-guard refactor) ----------
class TestCheckout:
    def test_checkout_starter_returns_stripe_url(self, vet1):
        r = vet1.post(f"{API}/payments/checkout", json={
            "lookup_key": "vetaura_starter_monthly",
            "origin_url": BASE_URL,
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert "checkout_url" in data and data["checkout_url"]
        assert "stripe.com" in data["checkout_url"], data["checkout_url"]

    def test_checkout_bundle_growth_plus_scribe(self, vet1):
        r = vet1.post(f"{API}/payments/checkout-bundle", json={
            "core_lookup_key": "vetaura_growth_monthly",
            "attach_scribe": True,
            "scribe_quantity": 2,
            "origin_url": BASE_URL,
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert "checkout_url" in data and "stripe.com" in data["checkout_url"]
        assert data.get("bundle_applied") is True


# ---------- Regression: twilio invalid creds (credentials_service.set_twilio) ----------
class TestTwilioInvalidCreds:
    def test_fake_creds_return_400(self, vet1):
        r = vet1.post(f"{API}/integrations/twilio", json={
            "account_sid": "AC" + "a" * 32,
            "api_key_sid": "SK" + "a" * 32,
            "api_key_secret": "fakesecretbutlongenough",
        })
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"
        detail = r.json().get("detail", "")
        assert detail.lower().startswith("twilio credentials invalid"), detail


# ---------- Regression: scribe templates ----------
class TestScribeTemplates:
    def test_vet1_has_builtin_templates(self, vet1):
        r = vet1.get(f"{API}/scribe/templates")
        assert r.status_code == 200, r.text
        arr = r.json()
        assert isinstance(arr, list) and len(arr) >= 5

    def test_vet2_isolation(self, vet1, vet2):
        # Create custom template as vet1
        name = f"TEST_iter7_{uuid.uuid4().hex[:6]}"
        r = vet1.post(f"{API}/scribe/templates", json={
            "name": name,
            "sections": ["S", "O", "A", "P"],
            "language": "en",
        })
        # Endpoint may return 200 or 201
        assert r.status_code in (200, 201), r.text

        # vet2 should not see it
        r2 = vet2.get(f"{API}/scribe/templates")
        assert r2.status_code == 200
        names = [t.get("name") for t in r2.json()]
        assert name not in names, f"multi-tenancy leak: vet2 sees vet1's template {name}"


# ---------- Regression: compliance profile ----------
class TestCompliance:
    def test_profile_readiness_and_checklist(self, vet1):
        r = vet1.get(f"{API}/compliance/sms/profile")
        assert r.status_code == 200, r.text
        d = r.json()
        assert "readiness" in d
        assert isinstance(d.get("checklist_definitions"), list)
        assert len(d["checklist_definitions"]) == 11


# ---------- Regression: SMS webhook (STOP/HELP) ----------
class TestSmsWebhook:
    WEBHOOK_TOKEN = "test_iter7_wh_tok"
    TEST_NUMBER = "+15550000000"
    NEW_FROM = "+15551239999"

    @pytest.fixture(scope="class")
    def seed(self, vet1_me):
        clinic_id = vet1_me["clinic_id"]
        from motor.motor_asyncio import AsyncIOMotorClient
        from dotenv import load_dotenv
        load_dotenv("/app/backend/.env")
        import sys
        sys.path.insert(0, "/app/backend")
        from crypto_service import encrypt as _encrypt

        async def _seed():
            client = AsyncIOMotorClient(os.environ["MONGO_URL"])
            db = client[os.environ["DB_NAME"]]
            await db.twilio_credentials.update_one(
                {"clinic_id": clinic_id},
                {"$set": {
                    "clinic_id": clinic_id,
                    "account_sid": "AC" + "s" * 32,
                    "api_key_sid": "SK" + "s" * 32,
                    "api_key_secret_encrypted": _encrypt("dummy_secret"),
                    "messaging_service_sid": "MGseed",
                    "webhook_token": self.WEBHOOK_TOKEN,
                    "friendly_name": "Iter7Seed",
                }},
                upsert=True,
            )
            await db.twilio_numbers.update_one(
                {"clinic_id": clinic_id, "phone_number": self.TEST_NUMBER},
                {"$set": {"clinic_id": clinic_id, "phone_number": self.TEST_NUMBER, "sid": "PNiter7"}},
                upsert=True,
            )
            # clear prior state for our fresh From number
            await db.consent_events.delete_many({"clinic_id": clinic_id, "phone_e164": self.NEW_FROM})
            await db.consent_records.delete_many({"clinic_id": clinic_id, "phone_e164": self.NEW_FROM})
            client.close()

        asyncio.run(_seed())
        return clinic_id

    def _post(self, clinic_id, body, from_num=None):
        url = f"{API}/twilio/sms/inbound/{clinic_id}/{self.WEBHOOK_TOKEN}"
        return requests.post(url, data={
            "From": from_num or self.NEW_FROM,
            "To": self.TEST_NUMBER,
            "Body": body,
        }, headers={"Content-Type": "application/x-www-form-urlencoded"})

    def test_stop_returns_unsubscribed(self, seed):
        r = self._post(seed, "STOP")
        assert r.status_code == 200, r.text
        assert "unsubscribed" in r.text.lower(), r.text

    def test_help_mentions_stop(self, seed):
        r = self._post(seed, "HELP", from_num="+15551239998")
        assert r.status_code == 200, r.text
        assert "STOP" in r.text or "stop" in r.text.lower()


# ---------- Regression: team invitations + signup ----------
class TestInvitations:
    def test_create_invite_and_signup(self, vet1, vet1_me):
        email = f"test_iter7_inv_{uuid.uuid4().hex[:6]}@example.com"
        r = vet1.post(f"{API}/team/invitations", json={
            "email": email, "role": "tech", "name": "Iter7 Invitee",
        })
        assert r.status_code == 200, r.text
        token = r.json().get("token")
        assert token

        s = requests.Session()
        s.headers["Content-Type"] = "application/json"
        r2 = s.post(f"{API}/auth/signup", json={
            "email": email, "password": PASS, "name": "Iter7 Invitee",
            "clinic_name": "ignored", "invite_token": token,
        })
        assert r2.status_code == 200, r2.text
        tok = r2.json().get("token") or r2.json().get("access_token")
        assert tok
        s.headers["Authorization"] = f"Bearer {tok}"
        me = s.get(f"{API}/auth/me").json()
        assert me["clinic_id"] == vet1_me["clinic_id"]
        assert me["role"] == "tech"


# ---------- Regression: SMS send without connected messaging service returns 400 not 500 ----------
class TestSmsSendGated:
    def test_send_returns_400_not_500(self, vet1):
        r = vet1.post(f"{API}/twilio/sms/send", json={
            "phone_e164": "+15551110000",
            "body": "hello test iter7",
        })
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"
        text = r.text.lower()
        assert (
            "blocked" in text
            or "not connected" in text
            or "brand" in text
            or "campaign" in text
            or "not approved" in text
            or "consent" in text
            or "messaging service" in text
        ), r.text
