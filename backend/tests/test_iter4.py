"""Iteration 4 — Vetaura features: pricing catalog, scribe templates, try-it wizard,
bundle checkout, Twilio scaffolding (voice/sms webhooks), voice usage summary."""
import os
import time
import uuid
import asyncio
import wave
import struct
import io
import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv(Path(__file__).resolve().parents[2] / "frontend" / ".env", override=False)

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "https://pet-care-helper-1.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

TS = int(time.time())


def _email(tag):
    return f"TEST_iter4_{tag}_{TS}_{uuid.uuid4().hex[:6]}@example.com"


def h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def acc1(sess):
    email = _email("A")
    r = sess.post(f"{API}/auth/signup", json={
        "email": email, "password": "strongpass123",
        "name": "Iter4 Vet A", "clinic_name": "TEST Iter4 Clinic A"
    })
    assert r.status_code == 200, r.text
    d = r.json()
    return {"email": email, "token": d["token"], "clinic_id": d["user"]["clinic_id"]}


@pytest.fixture(scope="module")
def acc2(sess):
    email = _email("B")
    r = sess.post(f"{API}/auth/signup", json={
        "email": email, "password": "strongpass123",
        "name": "Iter4 Vet B", "clinic_name": "TEST Iter4 Clinic B"
    })
    assert r.status_code == 200, r.text
    d = r.json()
    return {"email": email, "token": d["token"], "clinic_id": d["user"]["clinic_id"]}


# ---------------- Plans catalog ----------------
class TestPlans:
    def test_plans_returns_4_with_updated_prices(self, sess):
        r = sess.get(f"{API}/plans")
        assert r.status_code == 200
        plans = r.json().get("plans", [])
        by_key = {p["lookup_key"]: p for p in plans}
        for k in ("vetaura_starter_monthly", "vetaura_growth_monthly",
                  "vetaura_pro_monthly", "vetaura_scribe_addon_monthly"):
            assert k in by_key, f"missing plan {k}. got: {list(by_key)}"
        assert by_key["vetaura_starter_monthly"]["amount"] == 24900
        assert by_key["vetaura_growth_monthly"]["amount"] == 49900
        assert by_key["vetaura_pro_monthly"]["amount"] == 89900
        assert by_key["vetaura_scribe_addon_monthly"]["amount"] == 7900
        # Descriptions mention scribe / phone / voice
        combined = " ".join(p["description"].lower() for p in plans)
        assert "scribe" in combined
        assert "voice" in combined or "phone" in combined


# ---------------- Scribe Templates ----------------
class TestScribeTemplates:
    def test_lazy_seed_5_defaults(self, sess, acc1):
        r = sess.get(f"{API}/scribe/templates", headers=h(acc1["token"]))
        assert r.status_code == 200, r.text
        tpls = r.json()
        defaults = [t for t in tpls if t.get("is_default")]
        assert len(defaults) == 5, f"expected 5 default templates, got {len(defaults)}: {[t['slug'] for t in defaults]}"
        slugs = {t["slug"] for t in defaults}
        assert slugs == {"wellness", "dental", "dermatology", "euthanasia", "post_op"}
        for t in defaults:
            for k in ("subjective_hint", "objective_hint", "assessment_hint", "plan_hint"):
                assert t.get(k), f"{t['slug']} missing {k}"
            assert isinstance(t.get("required_fields"), list) and len(t["required_fields"]) > 0

    def test_create_patch_delete_custom(self, sess, acc1):
        payload = {
            "name": "TEST Custom Template",
            "description": "custom test",
            "subjective_hint": "Ask about diet",
            "objective_hint": "TPR",
            "assessment_hint": "assess",
            "plan_hint": "plan",
            "required_fields": ["TPR"],
        }
        r = sess.post(f"{API}/scribe/templates", headers=h(acc1["token"]), json=payload)
        assert r.status_code == 200, r.text
        tpl = r.json()
        assert tpl["is_default"] is False
        tid = tpl["id"]

        rp = sess.patch(f"{API}/scribe/templates/{tid}", headers=h(acc1["token"]),
                        json={"description": "updated"})
        assert rp.status_code == 200
        assert rp.json()["description"] == "updated"

        rd = sess.delete(f"{API}/scribe/templates/{tid}", headers=h(acc1["token"]))
        assert rd.status_code == 200

    def test_cannot_delete_built_in(self, sess, acc1):
        tpls = sess.get(f"{API}/scribe/templates", headers=h(acc1["token"])).json()
        default = next(t for t in tpls if t.get("is_default"))
        r = sess.delete(f"{API}/scribe/templates/{default['id']}", headers=h(acc1["token"]))
        assert r.status_code == 400

    def test_multi_tenant_isolation(self, sess, acc1, acc2):
        # acc1 creates custom
        r = sess.post(f"{API}/scribe/templates", headers=h(acc1["token"]),
                      json={"name": "TEST Isolate A"})
        assert r.status_code == 200
        tid_a = r.json()["id"]
        # acc2 lists
        r2 = sess.get(f"{API}/scribe/templates", headers=h(acc2["token"]))
        assert r2.status_code == 200
        ids_b = {t["id"] for t in r2.json()}
        assert tid_a not in ids_b, "cross-tenant leak of custom template"


# ---------------- SOAP with template ----------------
class TestSoapWithTemplate:
    def test_soap_uses_template(self, sess, acc1):
        tpls = sess.get(f"{API}/scribe/templates", headers=h(acc1["token"])).json()
        wellness = next(t for t in tpls if t["slug"] == "wellness")
        r = sess.post(f"{API}/scribe/soap", headers=h(acc1["token"]),
                      json={"transcript": "Bella 3yr dog, wellness visit, vaccines due, weight 22kg",
                            "template_id": wellness["id"]}, timeout=90)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("subjective", "objective", "assessment", "plan"):
            assert k in d and d[k], f"missing {k}"


# ---------------- Whisper transcribe (small synthetic WAV) ----------------
class TestTranscribe:
    def test_transcribe_wav(self, sess, acc1):
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(16000)
            # 0.5s of a 440Hz beep
            frames = b"".join(struct.pack("<h", int(20000 * ((i % 36) - 18) / 18)) for i in range(8000))
            wf.writeframes(frames)
        buf.seek(0)
        files = {"audio": ("beep.wav", buf.getvalue(), "audio/wav")}
        r = requests.post(f"{API}/scribe/transcribe",
                          headers={"Authorization": f"Bearer {acc1['token']}"},
                          files=files, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "transcript" in d
        assert isinstance(d["transcript"], str)


# ---------------- Try-it wizard ----------------
class TestTryIt:
    demo_id = None

    def test_try_it_no_auth(self, sess):
        r = sess.post(f"{API}/marketing/try-it", json={"url": "https://vcahospitals.com/"}, timeout=45)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("demo_clinic_id", "").startswith("demo_")
        assert d["profile"]["clinic_name"]
        assert d["receptionist_path"] == f"/r/{d['demo_clinic_id']}"
        assert d.get("expires_at")
        TestTryIt.demo_id = d["demo_clinic_id"]

    def test_public_receptionist_config(self, sess):
        assert TestTryIt.demo_id
        r = sess.get(f"{API}/receptionist/public/{TestTryIt.demo_id}")
        assert r.status_code == 200
        d = r.json()
        assert d.get("clinic_name")
        assert "greeting" in d

    def test_public_chat_no_auth(self, sess):
        assert TestTryIt.demo_id
        r = sess.post(f"{API}/receptionist/chat", json={
            "clinic_id": TestTryIt.demo_id,
            "session_id": f"test_{uuid.uuid4().hex[:8]}",
            "message": "What are your hours?",
        }, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("reply")


# ---------------- Bundle Checkout ----------------
class TestBundleCheckout:
    def test_with_bundle(self, sess, acc1):
        r = sess.post(f"{API}/payments/checkout-bundle", headers=h(acc1["token"]), json={
            "core_lookup_key": "vetaura_growth_monthly",
            "origin_url": BASE_URL,
            "attach_scribe": True,
            "scribe_quantity": 2,
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert "checkout_url" in d
        assert "stripe.com" in d["checkout_url"]
        assert d.get("bundle_applied") is True

    def test_without_bundle(self, sess, acc1):
        r = sess.post(f"{API}/payments/checkout-bundle", headers=h(acc1["token"]), json={
            "core_lookup_key": "vetaura_growth_monthly",
            "origin_url": BASE_URL,
            "attach_scribe": False,
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("bundle_applied") is False


# ---------------- Twilio scaffolding ----------------
class TestTwilio:
    def test_status_unconfigured(self, sess, acc1):
        r = sess.get(f"{API}/twilio/status", headers=h(acc1["token"]))
        assert r.status_code == 200
        d = r.json()
        assert d["configured"] is False
        assert d["number"] is None

    def test_provision_returns_503(self, sess, acc1):
        r = sess.post(f"{API}/twilio/provision", headers=h(acc1["token"]),
                      json={"area_code": "415"})
        assert r.status_code == 503
        assert "not configured" in r.text.lower()

    def test_voice_inbound_unconfigured_number(self, sess):
        r = sess.post(f"{API}/twilio/voice/inbound", data={
            "To": "+15550000000", "From": "+15551234567", "CallSid": "CATEST"
        }, headers={"Content-Type": "application/x-www-form-urlencoded"})
        assert r.status_code == 200
        assert "<Response>" in r.text
        assert "not configured" in r.text.lower() or "hangup" in r.text.lower()

    def test_sms_inbound_unconfigured_number(self, sess):
        r = sess.post(f"{API}/twilio/sms/inbound", data={
            "To": "+15550000000", "From": "+15551234567", "Body": "hello"
        }, headers={"Content-Type": "application/x-www-form-urlencoded"})
        assert r.status_code == 200
        assert "<Response>" in r.text or "MessagingResponse" in r.text or "<Message>" in r.text


# ---------------- Twilio SMS + emergency keyword with DB-bound number ----------------
class TestTwilioSmsEmergency:
    def test_bind_number_and_sms_emergency(self, sess, acc1):
        phone = f"+1555{TS % 10000:04d}999"

        async def _bind():
            client = AsyncIOMotorClient(MONGO_URL)
            db = client[DB_NAME]
            # remove any prior binding on this phone (safety)
            await db.twilio_numbers.delete_many({"phone_number": phone})
            await db.twilio_numbers.insert_one({
                "id": str(uuid.uuid4()),
                "clinic_id": acc1["clinic_id"],
                "phone_sid": f"PN{uuid.uuid4().hex[:20]}",
                "phone_number": phone,
                "friendly_name": "TEST bound",
                "created_at": "2026-01-01T00:00:00+00:00",
            })
            client.close()

        asyncio.run(_bind())
        # Sanity-check the write from a separate connection
        async def _verify():
            c = AsyncIOMotorClient(MONGO_URL)
            d = await c[DB_NAME].twilio_numbers.find_one({"phone_number": phone})
            c.close()
            return d
        assert asyncio.run(_verify()) is not None, "twilio_numbers write did not persist"

        r = sess.post(f"{API}/twilio/sms/inbound", data={
            "To": phone, "From": "+15551234567", "Body": "my dog collapsed"
        }, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=60)
        assert r.status_code == 200, r.text
        # Should return TwiML with emergency text (typically from cfg.emergency_instructions)
        assert "<Response>" in r.text
        low = r.text.lower()
        assert "emergency" in low or "immediately" in low or "hospital" in low, f"expected emergency text in: {r.text[:400]}"

        # Verify a task was created for that clinic with priority=urgent
        tasks = sess.get(f"{API}/tasks", headers=h(acc1["token"])).json()
        urgent_sms = [t for t in tasks
                      if t.get("priority") == "urgent" and t.get("source") == "twilio_sms"]
        assert urgent_sms, f"expected urgent twilio_sms task; got sources: {[t.get('source') for t in tasks]}"


# ---------------- Voice usage summary + status webhook ----------------
class TestVoiceUsage:
    def test_summary_initial(self, sess, acc1):
        r = sess.get(f"{API}/voice/usage-summary", headers=h(acc1["token"]))
        assert r.status_code == 200
        d = r.json()
        for k in ("plan", "voice_minutes", "voice_minutes_cap", "overage_minutes", "overage_cost_cents", "sms_count"):
            assert k in d

    def test_status_webhook_meters_minutes(self, sess, acc1):
        # Bind a new number for this test
        phone = f"+1555{(TS+1) % 10000:04d}888"

        async def _bind():
            client = AsyncIOMotorClient(MONGO_URL)
            db = client[DB_NAME]
            await db.twilio_numbers.delete_many({"phone_number": phone})
            await db.twilio_numbers.insert_one({
                "id": str(uuid.uuid4()),
                "clinic_id": acc1["clinic_id"],
                "phone_sid": f"PN{uuid.uuid4().hex[:20]}",
                "phone_number": phone,
                "created_at": "2026-01-01T00:00:00+00:00",
            })
            client.close()

        asyncio.run(_bind())

        before = sess.get(f"{API}/voice/usage-summary", headers=h(acc1["token"])).json()
        r = sess.post(f"{API}/twilio/voice/status", data={
            "To": phone, "From": "+15550000001",
            "CallSid": f"CA{uuid.uuid4().hex[:20]}",
            "CallStatus": "completed",
            "CallDuration": "120",
        }, headers={"Content-Type": "application/x-www-form-urlencoded"})
        assert r.status_code == 200
        after = sess.get(f"{API}/voice/usage-summary", headers=h(acc1["token"])).json()
        assert after["voice_minutes"] >= before["voice_minutes"] + 2.0 - 0.05, \
            f"expected +2 min; before={before['voice_minutes']} after={after['voice_minutes']}"
