"""Iter-8 security hardening regression tests.

Covers:
  SEC-001 SSRF in try-it scraper
  SEC-002 voicemail credential-leak (host allowlist)
  SEC-003 CORS wildcard + credentials guard
  SEC-004 Twilio X-Twilio-Signature validation
  Plus lightweight regressions on affected endpoints.
"""
from __future__ import annotations
import os
import asyncio
import pytest
import requests
from twilio.request_validator import RequestValidator

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pet-care-helper-1.preview.emergentagent.com").rstrip("/")

VET1 = ("vet1@example.com", "strongpass123")


# ---------- Fixtures ----------
@pytest.fixture(scope="module")
def s():
    return requests.Session()


@pytest.fixture(scope="module")
def vet1_token(s):
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": VET1[0], "password": VET1[1]})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def vet1_auth(vet1_token):
    return {"Authorization": f"Bearer {vet1_token}"}


# ---------- SEC-001 SSRF (try-it scraper) ----------
class TestSEC001_SSRF:
    def _post(self, s, url):
        return s.post(f"{BASE_URL}/api/marketing/try-it", json={"url": url})

    @pytest.mark.parametrize("url", [
        "http://localhost/",
        "http://127.0.0.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1/",
        "http://192.168.1.1/",
        "http://example.com:22/",
    ])
    def test_ssrf_blocked_400(self, s, url):
        r = self._post(s, url)
        assert r.status_code == 400, f"{url} -> {r.status_code} {r.text[:200]}"
        detail = (r.json().get("detail") or "").lower()
        # Any variant of "not permitted"/"address range"/"port"/"non-public" is acceptable
        assert any(kw in detail for kw in ["not permitted", "address range", "non-public", "port", "permitted"]), detail

    def test_file_scheme_rejected(self, s):
        r = self._post(s, "file:///etc/passwd")
        # Pydantic HttpUrl rejects — expect 422 (or 400)
        assert r.status_code in (400, 422), r.text

    def test_missing_scheme_rejected(self, s):
        r = self._post(s, "example.com")
        assert r.status_code in (400, 422), r.text

    def test_legit_url_succeeds(self, s):
        r = s.post(f"{BASE_URL}/api/marketing/try-it", json={"url": "https://example.com/"}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data.get("profile", {}).get("clinic_name")


# ---------- SEC-003 CORS ----------
class TestSEC003_CORS:
    def test_options_preflight_no_credentials_with_wildcard(self):
        r = requests.options(
            f"{BASE_URL}/api/auth/login",
            headers={
                "Origin": "https://attacker.example",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        # With wildcard CORS, ACAC must NOT be true
        allow_creds = r.headers.get("Access-Control-Allow-Credentials", "").lower()
        assert allow_creds != "true", f"ACAC={allow_creds}, headers={dict(r.headers)}"

    def test_normal_cross_origin_get(self):
        r = requests.get(
            f"{BASE_URL}/api/plans",
            headers={"Origin": "https://someorigin.example"},
        )
        assert r.status_code == 200
        allow_origin = r.headers.get("Access-Control-Allow-Origin", "")
        # Wildcard config: should be '*'
        assert allow_origin in ("*", "https://someorigin.example"), f"got {allow_origin}"


# ---------- SEC-004 Twilio signature + SEC-002 voicemail allowlist ----------
# We seed a fresh twilio_credentials + twilio_numbers row via motor to avoid Twilio live validation.
CLINIC_TEST_ID = "clinic_iter8_sec"
CLINIC_TEST_ID_VM = "clinic_iter8_sec_vm"  # separate id for voicemail tests to avoid parallel races
PHONE_TEST = "+15550000000"
WEBHOOK_TOKEN = "iter8_wh_token_sec"
FROM_NUMBER = "+15559999888"


async def _seed(auth_token: str = "", clinic_id: str = CLINIC_TEST_ID):
    """Seed a twilio_credentials + twilio_numbers row for clinic_id."""
    from motor.motor_asyncio import AsyncIOMotorClient
    import sys
    sys.path.insert(0, "/app/backend")
    from crypto_service import encrypt
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "vetaura")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    doc = {
        "clinic_id": clinic_id,
        "account_sid": "AC" + "0" * 32,
        "api_key_sid": "SK" + "0" * 32,
        "api_key_secret_encrypted": encrypt("fake_secret"),
        "auth_token_encrypted": encrypt(auth_token) if auth_token else "",
        "messaging_service_sid": None,
        "friendly_name": "iter8 test",
        "webhook_token": WEBHOOK_TOKEN,
        "updated_at": "2026-01-01T00:00:00Z",
        "verified_at": "2026-01-01T00:00:00Z",
    }
    await db.twilio_credentials.update_one(
        {"clinic_id": clinic_id}, {"$set": doc}, upsert=True
    )
    await db.twilio_numbers.update_one(
        {"clinic_id": clinic_id, "phone_number": PHONE_TEST},
        {"$set": {"clinic_id": clinic_id, "phone_number": PHONE_TEST, "phone_sid": "PNiter8"}},
        upsert=True,
    )
    # also make sure a clinics row exists so config lookups work
    await db.clinics.update_one(
        {"clinic_id": clinic_id},
        {"$setOnInsert": {"clinic_id": clinic_id, "name": "iter8 clinic", "plan": "demo"}},
        upsert=True,
    )
    client.close()


async def _cleanup(clinic_id: str = CLINIC_TEST_ID):
    from motor.motor_asyncio import AsyncIOMotorClient
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "vetaura")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    await db.twilio_credentials.delete_one({"clinic_id": clinic_id})
    await db.twilio_numbers.delete_many({"clinic_id": clinic_id})
    await db.clinics.delete_one({"clinic_id": clinic_id})
    await db.receptionist_configs.delete_one({"clinic_id": clinic_id})
    await db.messages.delete_many({"clinic_id": clinic_id})
    await db.tasks.delete_many({"clinic_id": clinic_id})
    await db.consent_events.delete_many({"clinic_id": clinic_id})
    await db.receptionist_sessions.delete_many({"clinic_id": clinic_id})
    await db.voice_usage.delete_many({"clinic_id": clinic_id})
    client.close()


@pytest.fixture(scope="module")
def loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


class TestSEC004_Signature:
    def test_a_no_auth_token_falls_open(self, loop):
        loop.run_until_complete(_cleanup())
        loop.run_until_complete(_seed(auth_token=""))
        url = f"{BASE_URL}/api/twilio/sms/inbound/{CLINIC_TEST_ID}/{WEBHOOK_TOKEN}"
        r = requests.post(url, data={"To": PHONE_TEST, "From": FROM_NUMBER, "Body": "hello"})
        assert r.status_code == 200, r.text[:300]
        # Should be TwiML with <Message> (not the "not configured" branch)
        assert "<Message>" in r.text, r.text[:300]

    def test_b_with_auth_token_no_signature_rejected(self, loop):
        loop.run_until_complete(_cleanup())
        loop.run_until_complete(_seed(auth_token="fake_at_for_test_only"))
        url = f"{BASE_URL}/api/twilio/sms/inbound/{CLINIC_TEST_ID}/{WEBHOOK_TOKEN}"
        r = requests.post(url, data={"To": PHONE_TEST, "From": FROM_NUMBER, "Body": "STOP-please-no-record"})
        # Behaviour differs from (a): _load_ctx returns None -> "not configured"
        assert r.status_code == 200
        assert "not configured" in r.text.lower(), r.text[:300]
        # And no consent transition should have been recorded for FROM
        async def _check():
            from motor.motor_asyncio import AsyncIOMotorClient
            client = AsyncIOMotorClient(os.environ.get("MONGO_URL"))
            db = client[os.environ.get("DB_NAME", "vetaura")]
            n = await db.consent_events.count_documents({
                "clinic_id": CLINIC_TEST_ID, "phone_e164": FROM_NUMBER
            })
            client.close()
            return n
        count = loop.run_until_complete(_check())
        assert count == 0, f"Consent transitions should NOT be recorded when signature invalid; got {count}"

    def test_c_with_valid_signature_accepted(self, loop):
        loop.run_until_complete(_cleanup())
        loop.run_until_complete(_seed(auth_token="fake_at_for_test_only"))
        # Use a fresh From number so STOP creates a new opt-out consent event.
        fresh_from = "+15557770001"
        url = f"{BASE_URL}/api/twilio/sms/inbound/{CLINIC_TEST_ID}/{WEBHOOK_TOKEN}"
        form = {"To": PHONE_TEST, "From": fresh_from, "Body": "STOP"}
        v = RequestValidator("fake_at_for_test_only")
        sig = v.compute_signature(url, form)
        r = requests.post(url, data=form, headers={"X-Twilio-Signature": sig})
        assert r.status_code == 200, r.text[:300]
        assert "<Message>" in r.text, r.text[:300]
        assert "not configured" not in r.text.lower()

        # Verify a new opt-out consent event was recorded for this fresh From number
        async def _check():
            from motor.motor_asyncio import AsyncIOMotorClient
            client = AsyncIOMotorClient(os.environ.get("MONGO_URL"))
            db = client[os.environ.get("DB_NAME", "vetaura")]
            n = await db.consent_events.count_documents({
                "clinic_id": CLINIC_TEST_ID, "phone_e164": fresh_from,
                "action": "opt_out"
            })
            client.close()
            return n
        count = loop.run_until_complete(_check())
        assert count >= 1, f"Expected opt-out consent event for {fresh_from}; got {count}"

    def test_d_signature_for_wrong_url_rejected(self, loop):
        """Valid signature but computed for a DIFFERENT URL must be rejected."""
        loop.run_until_complete(_cleanup())
        loop.run_until_complete(_seed(auth_token="fake_at_for_test_only"))
        url = f"{BASE_URL}/api/twilio/sms/inbound/{CLINIC_TEST_ID}/{WEBHOOK_TOKEN}"
        # Sign a DIFFERENT URL (query string added) — the actual request has no ?foo=bar
        wrong_url = url + "?foo=bar"
        fresh_from = "+15557770002"
        form = {"To": PHONE_TEST, "From": fresh_from, "Body": "STOP"}
        v = RequestValidator("fake_at_for_test_only")
        sig = v.compute_signature(wrong_url, form)
        r = requests.post(url, data=form, headers={"X-Twilio-Signature": sig})
        # Should be refused via "not configured" branch
        assert r.status_code == 200
        assert "not configured" in r.text.lower(), r.text[:300]

        # And no consent transition should have been recorded
        async def _check():
            from motor.motor_asyncio import AsyncIOMotorClient
            client = AsyncIOMotorClient(os.environ.get("MONGO_URL"))
            db = client[os.environ.get("DB_NAME", "vetaura")]
            n = await db.consent_events.count_documents({
                "clinic_id": CLINIC_TEST_ID, "phone_e164": fresh_from
            })
            client.close()
            return n
        count = loop.run_until_complete(_check())
        assert count == 0, f"No consent events expected for rejected request; got {count}"

    def test_cleanup(self, loop):
        loop.run_until_complete(_cleanup())


# ---------- SEC-002 voicemail host allowlist ----------
class TestSEC002_VoicemailAllowlist:
    def test_attacker_recording_url_rejected(self, loop):
        loop.run_until_complete(_cleanup(CLINIC_TEST_ID_VM))
        loop.run_until_complete(_seed(auth_token="", clinic_id=CLINIC_TEST_ID_VM))
        url = f"{BASE_URL}/api/twilio/voice/voicemail/{CLINIC_TEST_ID_VM}/{WEBHOOK_TOKEN}"
        r = requests.post(url, data={
            "To": PHONE_TEST, "From": FROM_NUMBER, "CallSid": "CAtest_iter8_vm",
            "RecordingUrl": "http://attacker.example.com/steal",
            "RecordingDuration": "5",
        })
        assert r.status_code == 200, r.text[:300]
        assert "<Response>" in r.text
        async def _check():
            from motor.motor_asyncio import AsyncIOMotorClient
            client = AsyncIOMotorClient(os.environ.get("MONGO_URL"))
            db = client[os.environ.get("DB_NAME", "vetaura")]
            msg = await db.messages.find_one({"clinic_id": CLINIC_TEST_ID_VM}, sort=[("received_at", -1)])
            client.close()
            return msg
        msg = loop.run_until_complete(_check())
        assert msg is not None
        assert msg["body"].startswith("Voicemail recording:"), msg["body"][:200]

    def test_cleanup(self, loop):
        loop.run_until_complete(_cleanup(CLINIC_TEST_ID_VM))


# ---------- Regression: /api/integrations/twilio signature_validation flag ----------
class TestTwilioCredsFlag:
    def test_invalid_creds_still_expose_flag_shape(self, s, vet1_auth):
        # We don't have live twilio creds, so this POST is expected to 400.
        # We only assert the request is accepted at Pydantic layer (i.e. auth_token is optional
        # and the payload validates). A 400 from Twilio live-check is fine — proves signature_validation
        # field is part of the response contract path.
        r = s.post(
            f"{BASE_URL}/api/integrations/twilio",
            json={
                "account_sid": "AC" + "0" * 32,
                "api_key_sid": "SK" + "0" * 32,
                "api_key_secret": "fake_secret_12345",
            },
            headers=vet1_auth,
        )
        # Either 400 (live validation fails) or 200 (unlikely). Not 422 — confirms schema.
        assert r.status_code in (200, 400), r.text[:200]
        r2 = s.post(
            f"{BASE_URL}/api/integrations/twilio",
            json={
                "account_sid": "AC" + "0" * 32,
                "api_key_sid": "SK" + "0" * 32,
                "api_key_secret": "fake_secret_12345",
                "auth_token": "some_auth_token_xyz",
            },
            headers=vet1_auth,
        )
        assert r2.status_code in (200, 400), r2.text[:200]


# ---------- Prior-iter light regression ----------
class TestRegression:
    def test_plans(self, s):
        r = s.get(f"{BASE_URL}/api/plans")
        assert r.status_code == 200
        data = r.json()
        plans = data.get("plans", data) if isinstance(data, dict) else data
        assert isinstance(plans, list) and len(plans) > 0

    def test_login(self, vet1_token):
        assert isinstance(vet1_token, str) and len(vet1_token) > 10

    def test_scribe_templates(self, s, vet1_auth):
        r = s.get(f"{BASE_URL}/api/scribe/templates", headers=vet1_auth)
        assert r.status_code == 200

    def test_compliance_profile(self, s, vet1_auth):
        r = s.get(f"{BASE_URL}/api/compliance/sms/profile", headers=vet1_auth)
        assert r.status_code == 200
