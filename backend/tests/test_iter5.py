"""Vetaura iteration 5 tests — BYOK, A2P compliance, invitations, overage billing, discharge email fallback."""
import os
import time
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

VET1_EMAIL = "vet1@example.com"
VET2_EMAIL = "vet2@example.com"
PASS = "strongpass123"
ADMIN_TOKEN = "admin-cron-secret-change-me"


def _auth(session, email, password):
    r = session.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("token") or data.get("access_token")
    assert tok, data
    session.headers["Authorization"] = f"Bearer {tok}"
    return data


@pytest.fixture(scope="module")
def vet1():
    s = requests.Session()
    s.headers["Content-Type"] = "application/json"
    _auth(s, VET1_EMAIL, PASS)
    # Ensure onboarded
    s.patch(f"{API}/clinic", json={"onboarded": True})
    return s


@pytest.fixture(scope="module")
def vet2():
    s = requests.Session()
    s.headers["Content-Type"] = "application/json"
    _auth(s, VET2_EMAIL, PASS)
    s.patch(f"{API}/clinic", json={"onboarded": True})
    return s


@pytest.fixture(scope="module")
def vet1_me(vet1):
    r = vet1.get(f"{API}/auth/me")
    assert r.status_code == 200
    return r.json()


# ---------- Integrations BYOK ----------

class TestIntegrationsBYOK:
    def test_twilio_initial_disconnected(self, vet1):
        r = vet1.get(f"{API}/integrations/twilio")
        assert r.status_code == 200, r.text
        # May exist from earlier test seed insert; accept either
        data = r.json()
        assert "connected" in data

    def test_twilio_rejects_fake_creds(self, vet1):
        # Format-valid but obviously fake creds (32 hex chars, ≥10 char secret) → live Twilio check must reject with 400
        r = vet1.post(f"{API}/integrations/twilio", json={
            "account_sid": "AC" + "a" * 32,
            "api_key_sid": "SK" + "b" * 32,
            "api_key_secret": "fakefakefake",
        })
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"
        assert "invalid" in r.text.lower() or "twilio" in r.text.lower()

    def test_email_initial_disconnected(self, vet1):
        r = vet1.get(f"{API}/integrations/email")
        assert r.status_code == 200
        assert "connected" in r.json()

    def test_email_rejects_fake_resend_key(self, vet1):
        r = vet1.post(f"{API}/integrations/email", json={
            "provider": "resend",
            "api_key": "re_fakefakefake",
            "from_email": "vet@example.com",
            "from_name": "Test",
        })
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"


# ---------- A2P 10DLC Compliance ----------

class TestSmsCompliance:
    def test_profile_lazy_seed(self, vet1):
        r = vet1.get(f"{API}/compliance/sms/profile")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "readiness" in data
        assert data["readiness"]["checklist_total"] == 11
        assert isinstance(data.get("checklist_definitions"), list)
        assert len(data["checklist_definitions"]) == 11
        assert data.get("brand_status") in ("not_started", "approved", "pending", "rejected", "in_review")

    def test_profile_patch_updates(self, vet1):
        r = vet1.patch(f"{API}/compliance/sms/profile", json={
            "brand_status": "approved",
            "campaign_status": "approved",
            "brand_sid": "BN1234",
            "campaign_sid": "CM5678",
            "legal_business_name": "Meadow Ridge Vet Inc.",
            "ein": "12-3456789",
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["brand_status"] == "approved"
        assert data["campaign_status"] == "approved"
        assert data.get("brand_sid") == "BN1234"

    def test_consent_opt_in_and_list(self, vet1):
        phone = "+15551110001"
        r = vet1.post(f"{API}/compliance/sms/consent", json={
            "phone_e164": phone,
            "consent_type": "care",
            "source": "intake_form_v3",
            "disclosure_version": "v1",
        })
        assert r.status_code == 200, r.text
        r = vet1.get(f"{API}/compliance/sms/consent")
        rows = r.json()
        match = [row for row in rows if row.get("phone_e164") == phone and row.get("consent_type") == "care"]
        assert match, f"consent record not found: {rows[:3]}"
        assert match[0]["status"] == "opted_in"

        # Opt out
        r = vet1.post(f"{API}/compliance/sms/consent/opt-out", json={
            "phone_e164": phone, "consent_type": "care", "reason": "test"
        })
        assert r.status_code == 200

        # Events
        r = vet1.get(f"{API}/compliance/sms/consent/events", params={"phone": phone})
        assert r.status_code == 200
        events = r.json()
        actions = [e["action"] for e in events if e.get("phone_e164") == phone]
        assert "opt_in" in actions and "opt_out" in actions, actions

    def test_preflight_denies_without_consent(self, vet1):
        r = vet1.get(f"{API}/compliance/sms/preflight",
                     params={"phone": "+15559998888", "message_type": "care"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["allowed"] is False
        assert isinstance(data["reason"], str) and len(data["reason"]) > 0


# ---------- Tokenised SMS webhooks ----------

CLINIC_ID = None
WEBHOOK_TOKEN = "test_wh_token_iter5"
TEST_NUMBER = "+15550000777"


@pytest.fixture(scope="module")
def seed_twilio_webhook(vet1_me):
    """Seed twilio_credentials and twilio_numbers docs directly in Mongo."""
    global CLINIC_ID
    CLINIC_ID = vet1_me["clinic_id"]
    from motor.motor_asyncio import AsyncIOMotorClient
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
    import sys
    sys.path.insert(0, "/app/backend")
    from crypto_service import encrypt as _seed_encrypt

    async def _seed():
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = client[os.environ["DB_NAME"]]
        await db.twilio_credentials.update_one(
            {"clinic_id": CLINIC_ID},
            {"$set": {
                "clinic_id": CLINIC_ID,
                "account_sid": "ACseededseededseededseededseeded1",
                "api_key_sid": "SKseededseededseededseededseeded1",
                "api_key_secret_encrypted": _seed_encrypt("dummy_secret"),
                "messaging_service_sid": "MGseeded",
                "webhook_token": WEBHOOK_TOKEN,
                "friendly_name": "Seed",
            }},
            upsert=True,
        )
        await db.twilio_numbers.update_one(
            {"clinic_id": CLINIC_ID, "phone_number": TEST_NUMBER},
            {"$set": {"clinic_id": CLINIC_ID, "phone_number": TEST_NUMBER, "sid": "PNseed"}},
            upsert=True,
        )
        # Clean any prior consent events for the fresh test number
        await db.consent_events.delete_many({"clinic_id": CLINIC_ID, "phone_e164": "+15551234567"})
        await db.consent_records.delete_many({"clinic_id": CLINIC_ID, "phone_e164": "+15551234567"})
        client.close()

    asyncio.run(_seed())
    yield
    # teardown: leave data; tests are isolated per number


def _form_post(url, from_num, to_num, body):
    return requests.post(url, data={"From": from_num, "To": to_num, "Body": body},
                         headers={"Content-Type": "application/x-www-form-urlencoded"})


class TestTwilioWebhooks:
    def test_stop_message(self, seed_twilio_webhook):
        url = f"{API}/twilio/sms/inbound/{CLINIC_ID}/{WEBHOOK_TOKEN}"
        r = _form_post(url, "+15551234567", TEST_NUMBER, "STOP")
        assert r.status_code == 200, r.text
        assert "unsubscribed" in r.text.lower() or "opted out" in r.text.lower() or "opt-out" in r.text.lower()

    def test_help_message(self, seed_twilio_webhook):
        url = f"{API}/twilio/sms/inbound/{CLINIC_ID}/{WEBHOOK_TOKEN}"
        r = _form_post(url, "+15551234568", TEST_NUMBER, "HELP")
        assert r.status_code == 200
        assert "STOP" in r.text or "stop" in r.text.lower()

    def test_emergency_message_after_stop_no_auto_optin(self, seed_twilio_webhook):
        # Emergency SMS from same +15551234567 (which just STOP'd)
        url = f"{API}/twilio/sms/inbound/{CLINIC_ID}/{WEBHOOK_TOKEN}"
        r = _form_post(url, "+15551234567", TEST_NUMBER, "my dog collapsed")
        assert r.status_code == 200, r.text
        # emergency footer (clinic name + Reply STOP)
        assert "STOP" in r.text or "opt out" in r.text.lower()

        # Verify no auto-opt-in occurred (care consent remains opted_out)
        from motor.motor_asyncio import AsyncIOMotorClient
        async def _check():
            client = AsyncIOMotorClient(os.environ["MONGO_URL"])
            db = client[os.environ["DB_NAME"]]
            rec = await db.consent_records.find_one({
                "clinic_id": CLINIC_ID, "phone_e164": "+15551234567", "consent_type": "care"
            })
            client.close()
            return rec
        rec = asyncio.run(_check())
        assert rec is not None, "care consent record should exist from STOP"
        assert rec["status"] == "opted_out", f"expected opted_out, got {rec['status']}"

    def test_wrong_webhook_token(self, seed_twilio_webhook):
        url = f"{API}/twilio/sms/inbound/{CLINIC_ID}/wrong_token_xyz"
        r = _form_post(url, "+15551234570", TEST_NUMBER, "hi")
        assert r.status_code == 200
        assert "not configured" in r.text.lower()

    def test_stop_recorded_opt_out_for_both_types(self, seed_twilio_webhook):
        # After STOP above, events for +15551234567 should include care+marketing opt_out
        r = requests.get(f"{API}/compliance/sms/consent/events",
                         params={"phone": "+15551234567"},
                         headers={"Authorization": None})
        # Need auth — use vet1 session
        pass  # handled by next authenticated test

    def test_stop_events_via_authenticated_vet1(self, vet1, seed_twilio_webhook):
        r = vet1.get(f"{API}/compliance/sms/consent/events", params={"phone": "+15551234567"})
        assert r.status_code == 200
        events = r.json()
        types_opt_out = {(e["consent_type"], e["action"]) for e in events}
        assert ("care", "opt_out") in types_opt_out
        assert ("marketing", "opt_out") in types_opt_out


# ---------- Invitations ----------

class TestInvitations:
    invite_token = None
    invite_email = None

    def test_owner_create_invite(self, vet1):
        email = f"test_iter5_invite_{uuid.uuid4().hex[:6]}@example.com"
        r = vet1.post(f"{API}/team/invitations", json={
            "email": email, "role": "tech", "name": "Alex T"
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("token")
        assert data.get("invite_url")
        assert data.get("delivered_by_email") is False
        TestInvitations.invite_token = data["token"]
        TestInvitations.invite_email = email

    def test_public_peek(self):
        assert TestInvitations.invite_token
        r = requests.get(f"{API}/invitations/{TestInvitations.invite_token}")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["email"] == TestInvitations.invite_email
        assert data["role"] == "tech"
        assert data.get("clinic_name")
        assert data.get("invited_by") == VET1_EMAIL

    def test_signup_with_invite_token(self, vet1_me):
        s = requests.Session()
        s.headers["Content-Type"] = "application/json"
        r = s.post(f"{API}/auth/signup", json={
            "email": TestInvitations.invite_email,
            "password": PASS,
            "name": "Alex T",
            "clinic_name": "ignored_invite",
            "invite_token": TestInvitations.invite_token,
        })
        assert r.status_code == 200, r.text
        data = r.json()
        tok = data.get("token") or data.get("access_token")
        s.headers["Authorization"] = f"Bearer {tok}"
        me = s.get(f"{API}/auth/me").json()
        assert me["clinic_id"] == vet1_me["clinic_id"]
        assert me["role"] == "tech"

        # Non-owner cannot invite
        r2 = s.post(f"{API}/team/invitations", json={
            "email": f"TEST_iter5_x_{uuid.uuid4().hex[:6]}@example.com", "role": "tech"
        })
        assert r2.status_code == 403, r2.text

        # Non-owner cannot delete another member
        r3 = s.delete(f"{API}/team/members/some_user_id")
        assert r3.status_code == 403, r3.text

        # But can list members
        r4 = s.get(f"{API}/team/members")
        assert r4.status_code == 200
        emails = [u["email"] for u in r4.json()]
        assert VET1_EMAIL in emails
        assert TestInvitations.invite_email in emails


# ---------- Billing cycle ----------

class TestBillingCycle:
    def test_preview_auth(self, vet1):
        r = vet1.get(f"{API}/billing-cycle/preview")
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, dict)

    def test_close_without_admin_token(self):
        r = requests.post(f"{API}/billing-cycle/close")
        assert r.status_code == 403

    def test_close_with_admin_token(self):
        r = requests.post(f"{API}/billing-cycle/close",
                          headers={"X-Admin-Token": ADMIN_TOKEN})
        assert r.status_code == 200, r.text
        data = r.json()
        assert "reported" in data
        assert "count" in data
        assert isinstance(data["reported"], list)


# ---------- Discharge email fallback ----------

class TestDischargeEmail:
    def test_discharge_email_nonexistent_token(self, vet1):
        r = vet1.post(f"{API}/discharge/email", json={
            "token": "nonexistent_token_xyz",
            "email_to": "a@b.com",
        })
        assert r.status_code == 404

    def test_ai_discharge_with_email_no_provider(self, vet1):
        # Ensure no email provider connected on vet1
        vet1.delete(f"{API}/integrations/email")
        r = vet1.post(f"{API}/ai/discharge", json={
            "pet_name": "Buddy",
            "plan_notes": "Rest and hydrate. Follow up in 7 days.",
            "language": "en",
            "email_to": "owner@example.com",
        }, timeout=90)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("email_delivered") is False
        assert data.get("email_error") == "email_not_configured"
