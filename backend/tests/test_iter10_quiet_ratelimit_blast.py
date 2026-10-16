# Iter-10: Quiet Hours, Login Rate Limiting/alerts, Marketing Bulk Blast + cron dispatch
import os
import time
import uuid
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

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
CRON_SECRET = os.environ.get("WEBHOOK_CRON_SECRET") or _env("/app/backend/.env", "WEBHOOK_CRON_SECRET")
PW = "strongpass123"
db = MongoClient(MONGO_URL)[DB_NAME]
QUIET_DEFAULTS = {"quiet_hours_enabled": True, "quiet_hours_start": "21:00", "quiet_hours_end": "08:00",
                  "quiet_hours_tz": "America/New_York", "quiet_days": [6]}


def clear_guard():
    db.login_attempts.delete_many({})
    db.login_lockouts.delete_many({})


def login(email, pw=PW, headers=None):
    return requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw}, headers=headers or {})


def token(email):
    clear_guard()
    r = login(email)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def H(t):
    return {"Authorization": f"Bearer {t}"}


def signup(email=None, clinic="TEST_Clinic"):
    email = email or f"test_{uuid.uuid4().hex[:10]}@example.com"
    r = requests.post(f"{BASE_URL}/api/auth/signup",
                      json={"email": email, "password": PW, "name": "Test User", "clinic_name": clinic})
    assert r.status_code == 200, r.text
    return email, r.json()


@pytest.fixture(scope="module")
def tok():
    clear_guard()
    t = {k: token(e) for k, e in [("vet1", "vet1@example.com"), ("owner2", "owner2@example.com"),
                                  ("vet2", "vet2@example.com")]}
    yield t
    clear_guard()
    cid = db.users.find_one({"email": "vet1@example.com"})["clinic_id"]
    db.sms_marketing_templates.delete_many({"clinic_id": cid, "name": {"$regex": "^TEST_"}})
    db.sms_campaigns.delete_many({"clinic_id": cid, "name": {"$regex": "^TEST_"}})


@pytest.fixture(scope="module")
def cid1():
    return db.users.find_one({"email": "vet1@example.com"})["clinic_id"]


def set_quiet(t, **kw):
    r = requests.patch(f"{BASE_URL}/api/compliance/sms/profile", json=kw, headers=H(t))
    assert r.status_code == 200, r.text
    return r.json()


def today_wd():
    return datetime.now(ZoneInfo("America/New_York")).weekday()


# ---------------- Quiet hours ----------------
class TestQuietHours:
    def test_defaults(self, tok):
        set_quiet(tok["vet1"], **QUIET_DEFAULTS)
        p = requests.get(f"{BASE_URL}/api/compliance/sms/profile", headers=H(tok["vet1"])).json()
        for k, v in QUIET_DEFAULTS.items():
            assert p[k] == v, (k, p[k])
        assert "active" in p["quiet_status"] and "next_send_at" in p["quiet_status"]

    @pytest.mark.parametrize("body", [{"quiet_hours_start": "25:00"}, {"quiet_hours_end": "9:5"},
                                      {"quiet_hours_tz": "Mars/Olympus"}, {"quiet_days": [7]}, {"quiet_days": [-1]}])
    def test_validation_422(self, tok, body):
        r = requests.patch(f"{BASE_URL}/api/compliance/sms/profile", json=body, headers=H(tok["vet1"]))
        assert r.status_code == 422, r.text

    def test_active_via_quiet_day_and_preflight(self, tok):
        try:
            p = set_quiet(tok["vet1"], quiet_days=[6, today_wd()])
            assert p["quiet_status"]["active"] is True
            nxt = datetime.fromisoformat(p["quiet_status"]["next_send_at"])
            assert nxt > datetime.now(timezone.utc)
            r = requests.get(f"{BASE_URL}/api/compliance/sms/preflight",
                             params={"phone": "+14155550142", "message_type": "marketing"}, headers=H(tok["vet1"])).json()
            assert r["allowed"] is False and "quiet" in r["reason"].lower()
            r = requests.get(f"{BASE_URL}/api/compliance/sms/preflight",
                             params={"phone": "+14155550142", "message_type": "care"}, headers=H(tok["vet1"])).json()
            assert "quiet" not in r["reason"].lower()
        finally:
            set_quiet(tok["vet1"], **QUIET_DEFAULTS)

    def test_active_via_time_window(self, tok):
        try:
            now = datetime.now(ZoneInfo("America/New_York"))
            s = (now - timedelta(hours=1)).strftime("%H:%M")
            e = (now + timedelta(hours=1)).strftime("%H:%M")
            p = set_quiet(tok["vet1"], quiet_hours_start=s, quiet_hours_end=e, quiet_days=[])
            assert p["quiet_days"] == []
            assert p["quiet_status"]["active"] is True
            p = set_quiet(tok["vet1"], quiet_hours_enabled=False)
            assert p["quiet_status"]["active"] is False
        finally:
            set_quiet(tok["vet1"], **QUIET_DEFAULTS)


# ---------------- Login rate limit ----------------
class TestLoginLockout:
    def test_email_lockout_throwaway(self):
        clear_guard()
        email = f"test_lock_{uuid.uuid4().hex[:8]}@example.com"
        codes = [login(email, "wrong").status_code for _ in range(5)]
        assert codes == [401] * 5
        r = login(email, "wrong")
        assert r.status_code == 423
        assert "Too many failed attempts" in r.json()["detail"]
        assert int(r.headers.get("Retry-After", "0")) > 0

    def test_real_user_lockout_alert_ack_events(self):
        clear_guard()
        email, s = signup()
        t = s["token"]
        for _ in range(5):
            assert login(email, "wrong").status_code == 401
        r = login(email, PW)  # correct pw still blocked
        assert r.status_code == 423
        alerts = requests.get(f"{BASE_URL}/api/security/alerts", headers=H(t)).json()
        assert len(alerts) >= 1 and alerts[0]["email"] == email and alerts[0]["acknowledged"] is False
        aid = alerts[0]["id"]
        assert requests.post(f"{BASE_URL}/api/security/alerts/{aid}/ack", headers=H(t)).status_code == 200
        alerts = requests.get(f"{BASE_URL}/api/security/alerts", headers=H(t)).json()
        assert [a for a in alerts if a["id"] == aid][0]["acknowledged"] is True
        assert requests.post(f"{BASE_URL}/api/security/alerts/nope/ack", headers=H(t)).status_code == 404
        ev = {e["event"] for e in requests.get(f"{BASE_URL}/api/security/auth-events", headers=H(t)).json()}
        assert {"login_failed", "account_locked"} <= ev, ev
        clear_guard()

    def test_success_resets_counter(self):
        clear_guard()
        email, _ = signup()
        for _ in range(3):
            assert login(email, "wrong").status_code == 401
        assert login(email).status_code == 200
        for _ in range(3):
            assert login(email, "wrong").status_code == 401
        assert login(email).status_code == 200
        clear_guard()

    def test_non_owner_403(self):
        clear_guard()
        email, s = signup()
        db.users.update_one({"email": email}, {"$set": {"role": "staff"}})
        for path in ["/api/security/alerts", "/api/security/auth-events"]:
            assert requests.get(f"{BASE_URL}{path}", headers=H(s["token"])).status_code == 403

    def test_ip_limit_and_xff_spoof(self):
        clear_guard()
        codes = [login(f"test_ip_{i}_{uuid.uuid4().hex[:6]}@example.com", "wrong").status_code for i in range(20)]
        assert codes == [401] * 20, codes
        r = login(f"test_ip_x_{uuid.uuid4().hex[:6]}@example.com", "wrong")
        assert r.status_code == 429, r.text
        r = login(f"test_ip_y_{uuid.uuid4().hex[:6]}@example.com", "wrong",
                  headers={"X-Forwarded-For": f"9.9.{uuid.uuid4().int % 250}.7"})
        assert r.status_code == 429, f"spoofed XFF bypassed IP bucket: {r.status_code}"
        clear_guard()

    def test_signup_ip_limit(self):
        clear_guard()
        codes = [requests.post(f"{BASE_URL}/api/auth/signup", json={"email": "vet1@example.com", "password": PW,
                                                                     "name": "x", "clinic_name": "x"}).status_code
                 for _ in range(20)]
        assert codes == [400] * 20, codes
        r = requests.post(f"{BASE_URL}/api/auth/signup", json={"email": "vet1@example.com", "password": PW,
                                                                "name": "x", "clinic_name": "x"})
        assert r.status_code == 429
        clear_guard()


# ---------------- Marketing blast ----------------
class TestMarketing:
    created_templates = []

    @pytest.fixture(autouse=True, scope="class")
    def _cleanup(self, tok):
        yield
        for tid in self.created_templates:
            requests.delete(f"{BASE_URL}/api/sms/marketing/templates/{tid}", headers=H(tok["vet1"]))
        set_quiet(tok["vet1"], **QUIET_DEFAULTS)

    def _tmpl(self, t, body="Hi {first_name}, {pet_name} is due for dental at {clinic_name}!"):
        r = requests.post(f"{BASE_URL}/api/sms/marketing/templates",
                          json={"name": f"TEST_{uuid.uuid4().hex[:5]}", "body": body}, headers=H(t))
        assert r.status_code == 200, r.text
        self.created_templates.append(r.json()["id"])
        return r.json()

    def _camp(self, t, tid, species="all"):
        r = requests.post(f"{BASE_URL}/api/sms/marketing/campaigns",
                          json={"name": f"TEST_camp_{uuid.uuid4().hex[:5]}", "template_id": tid, "species": species},
                          headers=H(t))
        assert r.status_code == 200, r.text
        return r.json()

    def test_template_rules(self, tok):
        r = requests.post(f"{BASE_URL}/api/sms/marketing/templates",
                          json={"name": "TEST_bad", "body": "Hi {owner_email}"}, headers=H(tok["vet1"]))
        assert r.status_code == 422
        t = self._tmpl(tok["vet1"])
        assert t["locked"] is True
        ids = [x["id"] for x in requests.get(f"{BASE_URL}/api/sms/marketing/templates", headers=H(tok["vet1"])).json()]
        assert t["id"] in ids
        assert t["id"] not in [x["id"] for x in requests.get(f"{BASE_URL}/api/sms/marketing/templates",
                                                              headers=H(tok["vet2"])).json()]
        for m in ("put", "patch"):
            assert getattr(requests, m)(f"{BASE_URL}/api/sms/marketing/templates/{t['id']}", json={"body": "x"},
                                        headers=H(tok["vet1"])).status_code in (404, 405)

    def test_non_owner_template_403(self):
        clear_guard()
        email, s = signup()
        db.users.update_one({"email": email}, {"$set": {"role": "staff"}})
        r = requests.post(f"{BASE_URL}/api/sms/marketing/templates", json={"name": "TEST_x", "body": "hi"},
                          headers=H(s["token"]))
        assert r.status_code == 403

    def test_preview(self, tok):
        t = self._tmpl(tok["vet1"])
        r = requests.post(f"{BASE_URL}/api/sms/marketing/audience/preview", json={"template_id": t["id"]},
                          headers=H(tok["vet1"])).json()
        assert r["eligible_count"] == 1, r
        assert set(r["excluded"]) == {"no_consent", "opted_out", "no_phone", "duplicate"}
        assert r["sample"][0]["phone_e164"] == "+14155550142"
        assert "{" not in r["sample"][0]["body"] and "Amelia" in r["sample"][0]["body"]
        # vet2 cannot preview vet1 template
        assert requests.post(f"{BASE_URL}/api/sms/marketing/audience/preview", json={"template_id": t["id"]},
                             headers=H(tok["vet2"])).status_code == 404

    def test_preview_species_and_zero_eligible(self, tok):
        t = self._tmpl(tok["vet1"])
        counts = {}
        for sp in ("Canine", "Feline"):
            counts[sp] = requests.post(f"{BASE_URL}/api/sms/marketing/audience/preview",
                                       json={"template_id": t["id"], "species": sp},
                                       headers=H(tok["vet1"])).json()["eligible_count"]
        assert sorted(counts.values()) in ([0, 1], [1, 1]), counts
        zero = [k for k, v in counts.items() if v == 0]
        if zero:
            r = requests.post(f"{BASE_URL}/api/sms/marketing/campaigns",
                              json={"name": "TEST_zero", "template_id": t["id"], "species": zero[0]},
                              headers=H(tok["vet1"]))
            assert r.status_code == 400

    def test_approval_rules_and_send(self, tok):
        set_quiet(tok["vet1"], **{**QUIET_DEFAULTS, "quiet_hours_enabled": False})
        t = self._tmpl(tok["vet1"])
        c = self._camp(tok["vet1"], t["id"])
        assert c["status"] == "pending_approval" and c["recipient_count"] == 1
        cid = c["id"]
        assert requests.post(f"{BASE_URL}/api/sms/marketing/campaigns/{cid}/approve",
                             headers=H(tok["vet1"])).status_code == 403
        assert requests.post(f"{BASE_URL}/api/sms/marketing/campaigns/{cid}/approve",
                             headers=H(tok["vet2"])).status_code == 404
        assert cid not in [x["id"] for x in requests.get(f"{BASE_URL}/api/sms/marketing/campaigns",
                                                         headers=H(tok["vet2"])).json()]
        r = requests.post(f"{BASE_URL}/api/sms/marketing/campaigns/{cid}/approve", headers=H(tok["owner2"]))
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "sending"
        for _ in range(20):
            camp = [x for x in requests.get(f"{BASE_URL}/api/sms/marketing/campaigns", headers=H(tok["vet1"])).json()
                    if x["id"] == cid][0]
            if camp["status"] == "completed":
                break
            time.sleep(1)
        assert camp["status"] == "completed", camp["status"]
        assert set(camp["results"]) == {"sent", "blocked", "failed"}
        assert sum(camp["results"].values()) == 1
        # double approve -> 400
        assert requests.post(f"{BASE_URL}/api/sms/marketing/campaigns/{cid}/approve",
                             headers=H(tok["owner2"])).status_code == 400

    def test_quiet_schedule_cancel_reject(self, tok):
        set_quiet(tok["vet1"], **{**QUIET_DEFAULTS, "quiet_days": [6, today_wd()]})
        t = self._tmpl(tok["vet1"])
        c = self._camp(tok["vet1"], t["id"])
        r = requests.post(f"{BASE_URL}/api/sms/marketing/campaigns/{c['id']}/approve", headers=H(tok["owner2"])).json()
        assert r["status"] == "scheduled"
        assert datetime.fromisoformat(r["scheduled_for"]) > datetime.now(timezone.utc)
        assert requests.post(f"{BASE_URL}/api/sms/marketing/campaigns/{c['id']}/cancel",
                             headers=H(tok["vet1"])).status_code == 200
        assert db.sms_campaigns.find_one({"id": c["id"]})["status"] == "cancelled"
        c2 = self._camp(tok["vet1"], t["id"])
        r = requests.post(f"{BASE_URL}/api/sms/marketing/campaigns/{c2['id']}/reject", json={"reason": "TEST"},
                          headers=H(tok["owner2"]))
        assert r.status_code == 200
        assert db.sms_campaigns.find_one({"id": c2["id"]})["status"] == "rejected"
        set_quiet(tok["vet1"], **QUIET_DEFAULTS)

    def test_readiness_400(self):
        clear_guard()
        email, s = signup()
        tk, clinic_id = s["token"], s["user"]["clinic_id"]
        owner = db.owners.find_one({"clinic_id": clinic_id})
        requests.post(f"{BASE_URL}/api/compliance/sms/consent", json={"phone_e164": owner["phone"],
                      "consent_type": "marketing", "source": "TEST", "disclosure_version": "v1"}, headers=H(tk))
        t = self._tmpl(tk)
        c = self._camp(tk, t["id"])
        db.sms_campaigns.update_one({"id": c["id"]}, {"$set": {"created_by": "someone_else@example.com"}})
        r = requests.post(f"{BASE_URL}/api/sms/marketing/campaigns/{c['id']}/approve", headers=H(tk))
        assert r.status_code == 400 and "Brand" in r.json()["detail"]

    def test_archive(self, tok):
        t = self._tmpl(tok["vet1"])
        assert requests.delete(f"{BASE_URL}/api/sms/marketing/templates/{t['id']}", headers=H(tok["vet2"])).status_code == 404
        assert requests.delete(f"{BASE_URL}/api/sms/marketing/templates/{t['id']}", headers=H(tok["vet1"])).status_code == 200
        assert requests.post(f"{BASE_URL}/api/sms/marketing/audience/preview", json={"template_id": t["id"]},
                             headers=H(tok["vet1"])).status_code == 404


# ---------------- Cron ----------------
class TestCron:
    def test_auth(self):
        u = f"{BASE_URL}/api/cron/sms-dispatch"
        assert requests.post(u).status_code == 401
        assert requests.post(u, headers={"Authorization": "Bearer wrong"}).status_code == 401
        wid = f"TEST_{uuid.uuid4().hex}"
        h = {"Authorization": f"Bearer {CRON_SECRET}", "X-Webhook-Id": wid}
        r = requests.post(u, headers=h)
        assert r.status_code == 200 and r.json()["ok"] is True and not r.json().get("duplicate")
        assert requests.post(u, headers=h).json().get("duplicate") is True

    def test_scheduled_dispatch(self, tok):
        try:
            set_quiet(tok["vet1"], **{**QUIET_DEFAULTS, "quiet_days": [6, today_wd()]})
            r = requests.post(f"{BASE_URL}/api/sms/marketing/templates",
                              json={"name": "TEST_cron", "body": "Hi {first_name}"}, headers=H(tok["vet1"])).json()
            tid = r["id"]
            c = requests.post(f"{BASE_URL}/api/sms/marketing/campaigns",
                              json={"name": "TEST_cron", "template_id": tid}, headers=H(tok["vet1"])).json()
            a = requests.post(f"{BASE_URL}/api/sms/marketing/campaigns/{c['id']}/approve", headers=H(tok["owner2"])).json()
            assert a["status"] == "scheduled"
            set_quiet(tok["vet1"], **QUIET_DEFAULTS)  # now outside quiet hours (if run on a weekday daytime)
            past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
            db.sms_campaigns.update_one({"id": c["id"]}, {"$set": {"scheduled_for": past}})
            r = requests.post(f"{BASE_URL}/api/cron/sms-dispatch", headers={"Authorization": f"Bearer {CRON_SECRET}"})
            assert r.status_code == 200
            for _ in range(15):
                st = db.sms_campaigns.find_one({"id": c["id"]})["status"]
                if st not in ("scheduled", "sending"):
                    break
                time.sleep(1)
            assert st == "completed", st
            requests.delete(f"{BASE_URL}/api/sms/marketing/templates/{tid}", headers=H(tok["vet1"]))
        finally:
            set_quiet(tok["vet1"], **QUIET_DEFAULTS)
