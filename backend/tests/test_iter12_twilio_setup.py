# Iter-12: Twilio setup wizard APIs (setup/check/health, roles, throttle) + iter-11 regression fixes
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests
from pymongo import MongoClient


def _env(path, key):
    for line in open(path):
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"')


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _env("/app/frontend/.env", "REACT_APP_BACKEND_URL")).rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL") or _env("/app/backend/.env", "MONGO_URL")
DB_NAME = os.environ.get("DB_NAME") or _env("/app/backend/.env", "DB_NAME")
PUBLIC_APP_URL = _env("/app/backend/.env", "PUBLIC_APP_URL")
PW = "strongpass123"
db = MongoClient(MONGO_URL)[DB_NAME]
T = f"{BASE_URL}/api/integrations/twilio"
FAKE = {"account_sid": "AC" + "a" * 32, "api_key_sid": "SK" + "b" * 32, "api_key_secret": "fakesecret1234567890",
        "messaging_service_sid": "MG" + "c" * 32}


def H(t):
    return {"Authorization": f"Bearer {t}"}


def login(email):
    db.login_attempts.delete_many({})
    db.login_lockouts.delete_many({})
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": PW})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def signup(tag):
    db.login_attempts.delete_many({})
    email = f"test_iter12_{tag}_{uuid.uuid4().hex[:6]}@example.com"
    r = requests.post(f"{BASE_URL}/api/auth/signup",
                      json={"email": email, "password": PW, "name": "TEST User", "clinic_name": f"TEST_iter12_{tag}"})
    assert r.status_code == 200, r.text
    return email, r.json()["token"], r.json()["user"]["clinic_id"], r.json()["user"]["user_id"]


@pytest.fixture(scope="module")
def ctx():
    c = {"vet1": login("vet1@example.com")}
    u = db.users.find_one({"email": "vet1@example.com"})
    c["cid1"] = u["clinic_id"]
    orig_setup = db.twilio_setup.find_one({"clinic_id": c["cid1"]}, {"_id": 0})
    # reception user inside vet1 clinic
    em, tok, own_cid, _ = signup("rec")
    db.users.update_one({"email": em}, {"$set": {"role": "reception", "clinic_id": c["cid1"]}})
    c["rec"], c["rec_email"], c["rec_cid"] = tok, em, own_cid
    # fresh owner clinic (no Twilio)
    em2, tok2, cid2, uid2 = signup("own")
    c["fresh"], c["fresh_email"], c["fresh_cid"], c["fresh_uid"] = tok2, em2, cid2, uid2
    db.twilio_setup_checks.delete_many({"clinic_id": c["cid1"]})
    yield c
    db.twilio_setup_checks.delete_many({"clinic_id": {"$in": [c["cid1"], cid2]}})
    if orig_setup:
        db.twilio_setup.replace_one({"clinic_id": c["cid1"]}, orig_setup, upsert=True)
    else:
        db.twilio_setup.delete_one({"clinic_id": c["cid1"]})
    for cid in (own_cid, cid2):
        for coll in ("twilio_setup", "care_items", "reminder_sends", "reminder_settings", "patients", "owners", "clinics"):
            db[coll].delete_many({"clinic_id": cid})
    db.phone_verify_attempts.delete_many({"user_id": uid2})
    db.phone_verifications.delete_many({"user_id": uid2})
    db.users.delete_many({"email": {"$in": [em, em2]}})


# ---------- GET/PUT /setup ----------
class TestSetup:
    def test_get_setup_connected(self, ctx):
        r = requests.get(f"{T}/setup", headers=H(ctx["vet1"]))
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["steps"] == ["account", "number", "messaging_service", "a2p", "api_key", "connect", "webhooks"]
        assert d["connected"] is True and isinstance(d["completed"], list)
        assert {"last_checks", "webhooks", "last_checked_at"} <= set(d)
        tok = db.twilio_credentials.find_one({"clinic_id": ctx["cid1"]})["webhook_token"]
        w = d["webhooks"]
        assert w["sms_url"] == f"{PUBLIC_APP_URL}/api/twilio/sms/inbound/{ctx['cid1']}/{tok}"
        assert w["voice_url"] == f"{PUBLIC_APP_URL}/api/twilio/voice/inbound/{ctx['cid1']}/{tok}"
        assert w["voice_status_callback"] == f"{PUBLIC_APP_URL}/api/twilio/voice/status/{ctx['cid1']}/{tok}"

    def test_get_setup_not_connected(self, ctx):
        d = requests.get(f"{T}/setup", headers=H(ctx["fresh"])).json()
        assert d["connected"] is False and d["webhooks"] is None and d["completed"] == []

    def test_put_setup_filters_orders_persists(self, ctx):
        r = requests.put(f"{T}/setup", json={"completed": ["a2p", "account", "bogus", "account"]}, headers=H(ctx["fresh"]))
        assert r.status_code == 200, r.text
        assert r.json()["completed"] == ["account", "a2p"]
        assert requests.get(f"{T}/setup", headers=H(ctx["fresh"])).json()["completed"] == ["account", "a2p"]

    def test_put_setup_too_many(self, ctx):
        r = requests.put(f"{T}/setup", json={"completed": ["account"] * 8}, headers=H(ctx["fresh"]))
        assert r.status_code == 422

    def test_non_owner_forbidden_but_can_read(self, ctx):
        h = H(ctx["rec"])
        assert requests.get(f"{T}/setup", headers=h).status_code == 200
        assert requests.put(f"{T}/setup", json={"completed": ["account"]}, headers=h).status_code == 403
        assert requests.post(f"{T}/check", json=FAKE, headers=h).status_code == 403
        assert requests.post(f"{T}/health", headers=h).status_code == 403

    def test_unauth(self):
        assert requests.get(f"{T}/setup").status_code == 401
        assert requests.post(f"{T}/check", json=FAKE).status_code == 401


# ---------- /check and /health ----------
class TestChecks:
    def test_check_fake_creds_readonly(self, ctx):
        before_creds = db.twilio_credentials.find_one({"clinic_id": ctx["fresh_cid"]})
        r = requests.post(f"{T}/check", json=FAKE, headers=H(ctx["fresh"]))
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is False
        assert d["checks"][0]["key"] == "credentials" and d["checks"][0]["status"] == "fail"
        assert "Twilio rejected" in d["checks"][0]["detail"] and "Re-copy" in d["checks"][0]["detail"]
        assert before_creds is None and db.twilio_credentials.find_one({"clinic_id": ctx["fresh_cid"]}) is None
        s = db.twilio_setup.find_one({"clinic_id": ctx["fresh_cid"]}) or {}
        assert not s.get("last_checks"), "check must not persist results"

    @pytest.mark.parametrize("bad", [{"account_sid": "AC123"}, {"api_key_sid": "XX" + "b" * 32},
                                     {"messaging_service_sid": "MGshort"}, {"api_key_secret": "x"}])
    def test_check_malformed_422(self, ctx, bad):
        r = requests.post(f"{T}/check", json={**FAKE, **bad}, headers=H(ctx["fresh"]))
        assert r.status_code == 422, r.text
        assert isinstance(r.json()["detail"], list)

    def test_health_not_connected_400(self, ctx):
        r = requests.post(f"{T}/health", headers=H(ctx["fresh"]))
        assert r.status_code == 400 and "isn't connected" in r.json()["detail"]

    def test_health_connected_fake_records(self, ctx):
        r = requests.post(f"{T}/health", headers=H(ctx["vet1"]))
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is False and d["checks"][0]["key"] == "credentials" and d["checks"][0]["status"] == "fail"
        g = requests.get(f"{T}/setup", headers=H(ctx["vet1"])).json()
        assert g["last_checks"] == d["checks"] and g["last_checked_at"]

    def test_throttle_429(self, ctx):
        cid = ctx["fresh_cid"]
        now = datetime.now(timezone.utc).isoformat()
        db.twilio_setup_checks.delete_many({"clinic_id": cid})
        db.twilio_setup_checks.insert_many([{"clinic_id": cid, "at": now} for _ in range(19)])
        assert requests.post(f"{T}/check", json=FAKE, headers=H(ctx["fresh"])).status_code == 200
        r = requests.post(f"{T}/check", json=FAKE, headers=H(ctx["fresh"]))
        assert r.status_code == 429 and "Too many" in r.json()["detail"]
        # old entries (>10 min) don't count
        db.twilio_setup_checks.update_many({"clinic_id": cid}, {"$set": {"at": (datetime.now(timezone.utc) - timedelta(minutes=11)).isoformat()}})
        assert requests.post(f"{T}/check", json=FAKE, headers=H(ctx["fresh"])).status_code == 200
        db.twilio_setup_checks.delete_many({"clinic_id": cid})


# ---------- Regression: iter-11 fixes ----------
class TestRegressionIter11:
    def test_phone_start_counts_failed_attempts(self, ctx):
        h = H(ctx["fresh"])
        codes = [requests.post(f"{BASE_URL}/api/me/mobile/start", json={"phone": "+14155550111"}, headers=h).status_code
                 for _ in range(6)]
        assert codes[:5] == [400] * 5 and codes[5] == 429, codes
        assert db.phone_verify_attempts.count_documents({"user_id": ctx["fresh_uid"]}) == 5

    def test_reminder_index_shape(self):
        info = db.reminder_sends.index_information()
        assert "item_id_1_stage_1" not in info
        dk = info["dedupe_key_1"]
        assert dk.get("unique") and dk.get("sparse")

    def test_reminder_retry_up_to_3_and_manual_no_last_run_date(self, ctx):
        h, cid = H(ctx["fresh"]), ctx["fresh_cid"]
        pid = db.patients.find_one({"clinic_id": cid})["id"]
        db.care_items.delete_many({"clinic_id": cid})
        due = (datetime.now(timezone.utc).date() + timedelta(days=3)).isoformat()
        it = requests.post(f"{BASE_URL}/api/reminders/items", json={"patient_id": pid, "name": "TEST_Retry", "due_date": due},
                           headers=h).json()
        runs = [requests.post(f"{BASE_URL}/api/reminders/run", headers=h).json() for _ in range(4)]
        for r in runs[:3]:
            assert r["sent"] == 0 and r["blocked"] + r["failed"] == 1, runs
        assert sum(runs[3].values()) == 0, runs
        recs = list(db.reminder_sends.find({"item_id": it["id"]}))
        assert len(recs) == 3 and all("dedupe_key" not in x for x in recs)
        s = db.reminder_settings.find_one({"clinic_id": cid}) or {}
        assert s.get("last_run_at") and not s.get("last_run_date")

    def test_stale_processing_becomes_failed_and_sent_never_repeats(self, ctx):
        h, cid = H(ctx["fresh"]), ctx["fresh_cid"]
        pid = db.patients.find_one({"clinic_id": cid})["id"]
        db.care_items.delete_many({"clinic_id": cid})
        due = (datetime.now(timezone.utc).date() + timedelta(days=3)).isoformat()
        a = requests.post(f"{BASE_URL}/api/reminders/items", json={"patient_id": pid, "name": "TEST_Stale", "due_date": due}, headers=h).json()
        b = requests.post(f"{BASE_URL}/api/reminders/items", json={"patient_id": pid, "name": "TEST_Sent", "due_date": due}, headers=h).json()
        old = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()
        db.reminder_sends.insert_many([
            {"id": str(uuid.uuid4()), "clinic_id": cid, "item_id": a["id"], "stage": 14, "status": "processing", "at": old,
             "item_name": "TEST_Stale", "dedupe_key": f"{a['id']}:14"},
            {"id": str(uuid.uuid4()), "clinic_id": cid, "item_id": b["id"], "stage": 14, "status": "sent", "at": old,
             "item_name": "TEST_Sent", "dedupe_key": f"{b['id']}:14"}])
        r = requests.post(f"{BASE_URL}/api/reminders/run", headers=h).json()
        st = db.reminder_sends.find_one({"item_id": a["id"], "at": old})
        assert st["status"] == "failed" and "dedupe_key" not in st
        assert r["blocked"] + r["failed"] == 1, r  # stale item retried once; sent item untouched
        assert db.reminder_sends.count_documents({"item_id": b["id"]}) == 1

    def test_ts_parser(self):
        sys.path.insert(0, "/app/backend")
        from sms_campaigns import _ts
        a, b = _ts("2026-01-05T10:00:00Z"), _ts("2026-01-05T10:00:00+00:00")
        assert a == b and a.tzinfo is not None
        assert _ts("2026-01-05").tzinfo is not None and _ts("garbage") is None and _ts(None) is None

    def test_env_single_key_and_crypto_fails_fast(self):
        lines = [l for l in open("/app/backend/.env") if l.startswith("VETAURA_ENCRYPTION_KEY")]
        assert len(lines) == 1
        env = {k: v for k, v in os.environ.items() if k != "VETAURA_ENCRYPTION_KEY"}
        ok = subprocess.run([sys.executable, "-c", "import crypto_service as c; print(c.decrypt(c.encrypt('x')))"],
                            cwd="/app/backend", env=env, capture_output=True, text=True)
        assert ok.returncode == 0 and ok.stdout.strip() == "x", ok.stderr
        tmp = tempfile.mkdtemp()
        try:
            shutil.copy("/app/backend/crypto_service.py", tmp)
            bad = subprocess.run([sys.executable, "-c", "import crypto_service"], cwd=tmp, env=env, capture_output=True, text=True)
            assert bad.returncode != 0 and "VETAURA_ENCRYPTION_KEY is not set" in bad.stderr
        finally:
            shutil.rmtree(tmp)
