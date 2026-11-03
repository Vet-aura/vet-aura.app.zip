# Iter-11: Care reminders (items/settings/upcoming/run/cron), phone verification, blast test send + results
import hashlib
import os
import uuid
from datetime import datetime, timezone, timedelta, date

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
R = f"{BASE_URL}/api/reminders"
M = f"{BASE_URL}/api/sms/marketing"


def clear_guard():
    db.login_attempts.delete_many({})
    db.login_lockouts.delete_many({})


def token(email):
    clear_guard()
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": PW})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def H(t):
    return {"Authorization": f"Bearer {t}"}


def iso(dt):
    return dt.isoformat()


@pytest.fixture(scope="module")
def ctx():
    clear_guard()
    c = {k: token(e) for k, e in [("vet1", "vet1@example.com"), ("owner2", "owner2@example.com"),
                                  ("vet2", "vet2@example.com")]}
    c["cid1"] = db.users.find_one({"email": "vet1@example.com"})["clinic_id"]
    c["uid1"] = db.users.find_one({"email": "vet1@example.com"})["user_id"]
    c["cid2"] = db.users.find_one({"email": "vet2@example.com"})["clinic_id"]
    # staff user in vet1 clinic
    email = f"test_iter11_staff_{uuid.uuid4().hex[:6]}@example.com"
    r = requests.post(f"{BASE_URL}/api/auth/signup",
                      json={"email": email, "password": PW, "name": "TEST Staff", "clinic_name": "TEST_iter11"})
    assert r.status_code == 200, r.text
    own_cid = r.json()["user"]["clinic_id"]
    db.users.update_one({"email": email}, {"$set": {"role": "tech", "clinic_id": c["cid1"]}})
    c["staff"] = r.json()["token"]
    c["staff_email"], c["staff_own_cid"] = email, own_cid
    c["p1"] = db.patients.find_one({"clinic_id": c["cid1"]})["id"]
    c["p2"] = db.patients.find_one({"clinic_id": c["cid2"]})["id"]
    yield c
    clear_guard()
    db.care_items.delete_many({"clinic_id": {"$in": [c["cid1"], c["cid2"]]}, "name": {"$regex": "^TEST_"}})
    db.reminder_sends.delete_many({"item_name": {"$regex": "^TEST_"}})
    db.reminder_settings.update_one({"clinic_id": c["cid1"]}, {"$unset": {"enabled": "", "offsets": "", "send_hour": "", "template": ""}})
    db.phone_verifications.delete_many({"user_id": c["uid1"]})
    db.users.update_one({"user_id": c["uid1"]}, {"$unset": {"mobile_phone": "", "mobile_verified": "", "mobile_verified_at": ""}})
    db.users.delete_one({"email": email})
    db.sms_campaigns.delete_many({"clinic_id": c["cid1"], "name": {"$regex": "^TEST_"}})
    db.sms_marketing_templates.delete_many({"clinic_id": c["cid1"], "name": {"$regex": "^TEST_"}})


# ---------------- Care items CRUD + scoping ----------------
class TestCareItems:
    def test_seeded_items(self, ctx):
        r = requests.get(f"{R}/items", headers=H(ctx["vet1"]))
        assert r.status_code == 200
        names = {i["name"] for i in r.json() if i.get("created_by") == "seed"}
        assert {"Rabies booster", "Senior wellness bloodwork", "FVRCP booster", "DHPP booster",
                "Heartworm test", "Dental cleaning"} <= names, names
        assert all("_id" not in i for i in r.json())

    def test_signup_seeds_items(self, ctx):
        assert db.care_items.count_documents({"clinic_id": ctx["staff_own_cid"]}) == 6

    def test_crud_and_scope(self, ctx):
        t1, t2 = ctx["vet1"], ctx["vet2"]
        due = (date.today() + timedelta(days=5)).isoformat()
        r = requests.post(f"{R}/items", json={"patient_id": ctx["p1"], "kind": "vaccine", "name": "TEST_Lepto", "due_date": due}, headers=H(t1))
        assert r.status_code == 200, r.text
        it = r.json()
        assert it["status"] == "due" and it["due_date"] == due
        lst = requests.get(f"{R}/items", params={"patient_id": ctx["p1"]}, headers=H(t1)).json()
        assert any(x["id"] == it["id"] for x in lst) and all(x["patient_id"] == ctx["p1"] for x in lst)
        # cross-clinic
        assert not any(x["id"] == it["id"] for x in requests.get(f"{R}/items", headers=H(t2)).json())
        assert requests.patch(f"{R}/items/{it['id']}", json={"name": "TEST_hack"}, headers=H(t2)).status_code == 404
        assert requests.post(f"{R}/items/{it['id']}/complete", headers=H(t2)).status_code == 404
        assert requests.delete(f"{R}/items/{it['id']}", headers=H(t2)).status_code == 404
        assert requests.post(f"{R}/items", json={"patient_id": ctx["p2"], "kind": "vaccine", "name": "TEST_x", "due_date": due},
                             headers=H(t1)).status_code == 404
        # validation
        assert requests.post(f"{R}/items", json={"patient_id": ctx["p1"], "kind": "bogus", "name": "TEST_x", "due_date": due},
                             headers=H(t1)).status_code == 422
        # patch
        r = requests.patch(f"{R}/items/{it['id']}", json={"name": "TEST_Lepto2", "kind": "preventive"}, headers=H(t1))
        assert r.status_code == 200 and r.json()["name"] == "TEST_Lepto2" and r.json()["kind"] == "preventive"
        assert requests.patch(f"{R}/items/{it['id']}", json={}, headers=H(t1)).status_code == 400
        # delete
        assert requests.delete(f"{R}/items/{it['id']}", headers=H(t1)).status_code == 200
        assert requests.delete(f"{R}/items/{it['id']}", headers=H(t1)).status_code == 404


# ---------------- Settings ----------------
class TestSettings:
    def test_defaults(self, ctx):
        s = requests.get(f"{R}/settings", headers=H(ctx["vet1"])).json()
        assert s["enabled"] is True and s["offsets"] == [14, 0, -7] and s["send_hour"] == 10
        for f in ("{first_name}", "{pet_name}", "{item}", "{due_phrase}"):
            assert f in s["template"]

    def test_put_validation_and_roles(self, ctx):
        base = requests.get(f"{R}/settings", headers=H(ctx["vet1"])).json()
        body = {k: base[k] for k in ("enabled", "offsets", "send_hour", "template")}
        assert requests.put(f"{R}/settings", json=body, headers=H(ctx["staff"])).status_code == 403
        assert requests.put(f"{R}/settings", json={**body, "template": "Hi {owner_email} {pet_name} x"}, headers=H(ctx["vet1"])).status_code == 422
        assert requests.put(f"{R}/settings", json={**body, "offsets": [120]}, headers=H(ctx["vet1"])).status_code == 422
        assert requests.put(f"{R}/settings", json={**body, "offsets": [-61]}, headers=H(ctx["vet1"])).status_code == 422
        assert requests.put(f"{R}/settings", json={**body, "send_hour": 5}, headers=H(ctx["vet1"])).status_code == 422
        assert requests.put(f"{R}/settings", json={**body, "send_hour": 21}, headers=H(ctx["vet1"])).status_code == 422
        r = requests.put(f"{R}/settings", json={**body, "offsets": [0, 14, -7, 14], "send_hour": 11}, headers=H(ctx["vet1"]))
        assert r.status_code == 200 and r.json()["offsets"] == [14, 0, -7] and r.json()["send_hour"] == 11
        assert requests.get(f"{R}/settings", headers=H(ctx["vet1"])).json()["send_hour"] == 11
        r = requests.put(f"{R}/settings", json=body, headers=H(ctx["vet1"]))
        assert r.status_code == 200


# ---------------- Upcoming + run + dedupe + complete ----------------
class TestRun:
    def test_upcoming_run_dedupe_complete(self, ctx):
        t = ctx["vet1"]
        # create item due today on p1, owner needs phone
        p = db.patients.find_one({"id": ctx["p1"]})
        owner = db.owners.find_one({"id": p["owner_id"]})
        today = datetime.now(timezone.utc).date()  # close enough to clinic NY date in most hours
        it = requests.post(f"{R}/items", json={"patient_id": ctx["p1"], "kind": "vaccine", "name": "TEST_Today",
                                               "due_date": (today + timedelta(days=3)).isoformat()}, headers=H(t)).json()
        up = requests.get(f"{R}/upcoming", params={"days": 30}, headers=H(t))
        assert up.status_code == 200
        row = next((x for x in up.json() if x["item_id"] == it["id"]), None)
        assert row and row["stage"] == 14 and "send_on" in row and "care_consent" in row, up.json()
        assert requests.post(f"{R}/run", headers=H(ctx["staff"])).status_code == 403
        r1 = requests.post(f"{R}/run", headers=H(t))
        assert r1.status_code == 200, r1.text
        c1 = r1.json()
        assert set(c1) == {"sent", "blocked", "failed"}
        log = requests.get(f"{R}/log", headers=H(t)).json()
        mine = [l for l in log if l["item_id"] == it["id"]]
        assert len(mine) == 1 and mine[0]["stage"] == 14 and mine[0]["status"] in ("blocked", "failed")
        assert "Reply STOP to opt out." in mine[0]["body"] and "is due in 3 days" in mine[0]["body"]
        assert mine[0]["body"].startswith(f"Hi {owner['name'].split(' ')[0]}, a reminder that {p['name']}'s TEST_Today")
        r2 = requests.post(f"{R}/run", headers=H(t)).json()
        assert sum(r2.values()) == 0, r2
        # complete -> gone from upcoming
        assert requests.post(f"{R}/items/{it['id']}/complete", headers=H(t)).status_code == 200
        up = requests.get(f"{R}/upcoming", params={"days": 30}, headers=H(t)).json()
        assert not any(x["item_id"] == it["id"] for x in up)

    def test_consent_failed_vs_blocked(self, ctx):
        t = ctx["vet1"]
        p = db.patients.find_one({"id": ctx["p1"]})
        owner = db.owners.find_one({"id": p["owner_id"]})
        from_digits = "".join(ch for ch in owner["phone"] if ch.isdigit())
        e164 = "+" + (from_digits if len(from_digits) == 11 else "1" + from_digits)
        today = datetime.now(timezone.utc).date()
        # blocked without care consent
        prev = db.consent_records.find_one({"clinic_id": ctx["cid1"], "phone_e164": e164, "consent_type": "care"}, {"_id": 0})
        db.consent_records.delete_one({"clinic_id": ctx["cid1"], "phone_e164": e164, "consent_type": "care"})
        a = requests.post(f"{R}/items", json={"patient_id": ctx["p1"], "kind": "vaccine", "name": "TEST_NoConsent",
                                              "due_date": (today - timedelta(days=9)).isoformat()}, headers=H(t)).json()
        up = requests.get(f"{R}/upcoming", headers=H(t)).json()
        row = next(x for x in up if x["item_id"] == a["id"])
        assert row["care_consent"] == "none" and row["stage"] == -7
        requests.post(f"{R}/run", headers=H(t))
        la = next(l for l in requests.get(f"{R}/log", headers=H(t)).json() if l["item_id"] == a["id"])
        assert la["status"] == "blocked" and "consent" in la["reason"].lower()
        assert "9 days overdue" in la["body"]
        # with care consent -> failed (fake twilio 401)
        r = requests.post(f"{BASE_URL}/api/compliance/sms/consent", json={"phone_e164": e164, "consent_type": "care",
                          "source": "staff_manual", "disclosure_version": "v1"}, headers=H(t))
        assert r.status_code == 200, r.text
        b = requests.post(f"{R}/items", json={"patient_id": ctx["p1"], "kind": "vaccine", "name": "TEST_Consent",
                                              "due_date": today.isoformat()}, headers=H(t)).json()
        requests.post(f"{R}/run", headers=H(t))
        lb = next(l for l in requests.get(f"{R}/log", headers=H(t)).json() if l["item_id"] == b["id"])
        assert lb["status"] == "failed" and "401" in lb["reason"], lb
        # restore consent state
        db.consent_records.delete_one({"clinic_id": ctx["cid1"], "phone_e164": e164, "consent_type": "care"})
        if prev:
            db.consent_records.insert_one(prev)


# ---------------- Cron ----------------
class TestCron:
    def test_cron_auth_and_dedupe(self):
        u = f"{BASE_URL}/api/cron/care-reminders"
        assert requests.post(u).status_code == 401
        assert requests.post(u, headers={"Authorization": "Bearer wrong"}).status_code == 401
        wid = f"TEST_{uuid.uuid4().hex}"
        h = {"Authorization": f"Bearer {CRON_SECRET}", "X-Webhook-Id": wid}
        r = requests.post(u, headers=h)
        assert r.status_code == 200 and r.json().get("ok") is True and not r.json().get("duplicate")
        assert requests.post(u, headers=h).json().get("duplicate") is True
        db.cron_runs.delete_one({"run_id": wid})


# ---------------- Phone verification ----------------
class TestPhoneVerify:
    def test_flow(self, ctx):
        t, uid = ctx["vet1"], ctx["uid1"]
        U = f"{BASE_URL}/api/me/mobile"
        db.phone_verifications.delete_many({"user_id": uid})
        g = requests.get(U, headers=H(t)).json()
        assert set(g) == {"phone", "verified"}
        assert requests.post(f"{U}/start", json={"phone": "12345678"}, headers=H(t)).status_code == 400
        r = requests.post(f"{U}/start", json={"phone": "(415) 555-0100"}, headers=H(t))
        assert r.status_code == 400 and "Couldn't send the code" in r.json()["detail"], r.text
        assert db.phone_verifications.count_documents({"user_id": uid}) == 0
        # rate limit via seeding 5 recent starts
        now = datetime.now(timezone.utc)
        db.phone_verifications.insert_many([{"user_id": uid, "clinic_id": ctx["cid1"], "phone": "+14155550100", "code_hash": "x",
                                             "attempts": 0, "used": True, "created_at": iso(now), "expires_at": iso(now)} for _ in range(5)])
        assert requests.post(f"{U}/start", json={"phone": "+14155550100"}, headers=H(t)).status_code == 429
        db.phone_verifications.delete_many({"user_id": uid})
        # verify validation
        assert requests.post(f"{U}/verify", json={"code": "12345"}, headers=H(t)).status_code == 422
        assert requests.post(f"{U}/verify", json={"code": "abcdef"}, headers=H(t)).status_code == 422
        db.phone_verifications.insert_one({"user_id": uid, "clinic_id": ctx["cid1"], "phone": "+14155550100",
                                           "code_hash": hashlib.sha256(f"{uid}:123456".encode()).hexdigest(), "attempts": 0,
                                           "used": False, "created_at": iso(now), "expires_at": iso(now + timedelta(minutes=10))})
        r = requests.post(f"{U}/verify", json={"code": "000000"}, headers=H(t))
        assert r.status_code == 400 and "match" in r.json()["detail"]
        assert db.phone_verifications.find_one({"user_id": uid})["attempts"] == 1
        r = requests.post(f"{U}/verify", json={"code": "123456"}, headers=H(t))
        assert r.status_code == 200 and r.json() == {"phone": "+14155550100", "verified": True}
        u = db.users.find_one({"user_id": uid})
        assert u["mobile_phone"] == "+14155550100" and u["mobile_verified"] is True
        assert requests.get(U, headers=H(t)).json() == {"phone": "+14155550100", "verified": True}
        # used code cannot be replayed
        assert requests.post(f"{U}/verify", json={"code": "123456"}, headers=H(t)).status_code == 400
        assert requests.delete(U, headers=H(t)).status_code == 200
        assert requests.get(U, headers=H(t)).json() == {"phone": None, "verified": False}

    def test_lock_after_5_wrong(self, ctx):
        t, uid = ctx["vet1"], ctx["uid1"]
        U = f"{BASE_URL}/api/me/mobile"
        db.phone_verifications.delete_many({"user_id": uid})
        now = datetime.now(timezone.utc)
        db.phone_verifications.insert_one({"user_id": uid, "clinic_id": ctx["cid1"], "phone": "+14155550100",
                                           "code_hash": hashlib.sha256(f"{uid}:123456".encode()).hexdigest(), "attempts": 0,
                                           "used": False, "created_at": iso(now), "expires_at": iso(now + timedelta(minutes=10))})
        for _ in range(5):
            assert "match" in requests.post(f"{U}/verify", json={"code": "999999"}, headers=H(t)).json()["detail"]
        r = requests.post(f"{U}/verify", json={"code": "123456"}, headers=H(t))
        assert r.status_code == 400 and "expired" in r.json()["detail"].lower()
        db.phone_verifications.delete_many({"user_id": uid})


# ---------------- Blast test send + results ----------------
def _campaign(ctx, status="pending_approval", recipients=None):
    owners = list(db.owners.find({"clinic_id": ctx["cid1"]}).limit(3))
    recs = recipients or [{"owner_id": o["id"], "name": o["name"], "phone_e164": f"+1415555{9000 + i}", "body": "Hi TEST",
                           "status": "pending"} for i, o in enumerate(owners)]
    doc = {"id": str(uuid.uuid4()), "clinic_id": ctx["cid1"], "name": f"TEST_camp_{uuid.uuid4().hex[:5]}",
           "template_id": "x", "template_name": "TEST_t", "template_body": "Hi TEST", "species": "all",
           "recipients": recs, "recipient_count": len(recs), "status": status, "created_by": "owner2@example.com",
           "created_at": iso(datetime.now(timezone.utc))}
    db.sms_campaigns.insert_one({**doc})
    return doc


class TestBlastTest:
    def test_send_test(self, ctx):
        t, uid = ctx["vet1"], ctx["uid1"]
        c = _campaign(ctx)
        done = _campaign(ctx, status="completed")
        assert requests.post(f"{M}/campaigns/{c['id']}/test", headers=H(ctx["staff"])).status_code == 403
        assert requests.post(f"{M}/campaigns/{done['id']}/test", headers=H(t)).status_code == 400
        assert requests.post(f"{M}/campaigns/{c['id']}/test", headers=H(ctx["vet2"])).status_code == 404
        db.users.update_one({"user_id": uid}, {"$unset": {"mobile_phone": "", "mobile_verified": ""}})
        r = requests.post(f"{M}/campaigns/{c['id']}/test", headers=H(t))
        assert r.status_code == 400 and r.json()["detail"] == "Verify your mobile number in Settings first."
        db.users.update_one({"user_id": uid}, {"$set": {"mobile_phone": "+14155550100", "mobile_verified": True}})
        for i in range(5):
            r = requests.post(f"{M}/campaigns/{c['id']}/test", headers=H(t))
            assert r.status_code == 400 and r.json()["detail"].startswith("Test send failed"), r.text
        r = requests.post(f"{M}/campaigns/{c['id']}/test", headers=H(t))
        assert r.status_code == 429
        cdb = db.sms_campaigns.find_one({"id": c["id"]})
        assert len(cdb["tests"]) == 5 and all(x["status"] == "failed" and x["body"].startswith("[TEST]") for x in cdb["tests"])
        assert cdb["status"] == "pending_approval" and all(x["status"] == "pending" for x in cdb["recipients"])
        assert "results" not in cdb
        db.users.update_one({"user_id": uid}, {"$unset": {"mobile_phone": "", "mobile_verified": ""}})


class TestBlastResults:
    def test_results_attribution(self, ctx):
        t, cid = ctx["vet1"], ctx["cid1"]
        owners = list(db.owners.find({"clinic_id": cid}).limit(3))
        sent_at = datetime.now(timezone.utc) - timedelta(days=40)
        phones = [f"+1415555{9100 + i}" for i in range(3)]
        recs = [{"owner_id": owners[0]["id"], "name": owners[0]["name"], "phone_e164": phones[0], "body": "x", "status": "sent", "sent_at": iso(sent_at)},
                {"owner_id": owners[1]["id"], "name": owners[1]["name"], "phone_e164": phones[1], "body": "x", "status": "sent", "sent_at": iso(sent_at)},
                {"owner_id": owners[2]["id"], "name": owners[2]["name"], "phone_e164": phones[2], "body": "x", "status": "blocked", "reason": "no consent"}]
        c = _campaign(ctx, status="completed", recipients=recs)
        pet0 = db.patients.find_one({"clinic_id": cid, "owner_id": owners[0]["id"]})["id"]
        pet1 = db.patients.find_one({"clinic_id": cid, "owner_id": owners[1]["id"]})["id"]
        tag = "TEST_iter11_" + uuid.uuid4().hex[:6]
        db.receptionist_sessions.insert_many([
            {"clinic_id": cid, "from_number": phones[0], "tag": tag, "transcript": [{"role": "user", "text": "yes", "at": iso(sent_at + timedelta(days=1))}]},
            {"clinic_id": cid, "from_number": phones[1], "tag": tag, "transcript": [{"role": "user", "text": "late", "at": iso(sent_at + timedelta(days=8))}]}])
        db.consent_events.insert_one({"clinic_id": cid, "phone_e164": phones[0], "consent_type": "marketing", "action": "opt_out",
                                      "at": iso(sent_at + timedelta(days=2)), "tag": tag})
        db.appointments.insert_many([
            {"id": tag + "a", "clinic_id": cid, "patient_id": pet0, "datetime": iso(sent_at + timedelta(days=5)),
             "created_at": iso(sent_at - timedelta(days=60)), "tag": tag},
            {"id": tag + "b", "clinic_id": cid, "patient_id": pet1, "datetime": iso(sent_at + timedelta(days=31)),
             "created_at": iso(sent_at - timedelta(days=60)), "tag": tag}])
        try:
            assert requests.get(f"{M}/campaigns/{c['id']}/results", headers=H(ctx["vet2"])).status_code == 404
            r = requests.get(f"{M}/campaigns/{c['id']}/results", headers=H(t))
            assert r.status_code == 200, r.text
            s = r.json()["summary"]
            assert s["recipients"] == 3 and s["sent"] == 2 and s["blocked"] == 1 and s["failed"] == 0, s
            assert s["replied"] == 1 and s["opted_out"] == 1 and s["booked"] == 1, s
            assert s["reply_rate"] == 50.0 and s["opt_out_rate"] == 50.0 and s["booking_rate"] == 50.0
            rows = {x["owner_id"]: x for x in r.json()["rows"]}
            assert rows[owners[0]["id"]]["replied"]["text"] == "yes"
            assert rows[owners[1]["id"]]["replied"] is None and rows[owners[1]["id"]]["booked_at"] is None
            assert rows[owners[2]["id"]]["status"] == "blocked"
        finally:
            db.receptionist_sessions.delete_many({"tag": tag})
            db.consent_events.delete_many({"tag": tag})
            db.appointments.delete_many({"tag": tag})
