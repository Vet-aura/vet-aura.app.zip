# Iter-11: cron background gating (send_hour, quiet day, last_run_date) for care reminders
import time
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from test_iter11_reminders_verify_results import BASE_URL, CRON_SECRET, db, token, H

R = f"{BASE_URL}/api/reminders"


def _fire():
    wid = f"TEST_{uuid.uuid4().hex}"
    r = requests.post(f"{BASE_URL}/api/cron/care-reminders", headers={"Authorization": f"Bearer {CRON_SECRET}", "X-Webhook-Id": wid})
    assert r.status_code == 200
    time.sleep(6)
    db.cron_runs.delete_one({"run_id": wid})


def test_schedule_gating():
    t = token("vet1@example.com")
    cid = db.users.find_one({"email": "vet1@example.com"})["clinic_id"]
    prof = db.sms_compliance_profiles.find_one({"clinic_id": cid})
    tz = ZoneInfo(prof.get("quiet_hours_tz") or "America/New_York")
    local = datetime.now(tz)
    orig_qd = prof.get("quiet_days", [6])
    orig_settings = db.reminder_settings.find_one({"clinic_id": cid}, {"_id": 0}) or {}
    pid = db.patients.find_one({"clinic_id": cid})["id"]
    it = requests.post(f"{R}/items", json={"patient_id": pid, "kind": "vaccine", "name": "TEST_cron_item",
                                           "due_date": local.date().isoformat()}, headers=H(t)).json()
    try:
        base = {"enabled": True, "offsets": [14, 0, -7], "template": "Hi {first_name}, {pet_name}'s {item} {due_phrase}."}
        # 1) hour not reached -> no send
        if local.hour < 20:
            db.reminder_settings.update_one({"clinic_id": cid}, {"$set": {**base, "send_hour": 20, "last_run_date": None}}, upsert=True)
            _fire()
            assert db.reminder_sends.count_documents({"item_id": it["id"]}) == 0, "sent before send_hour"
        # 2) quiet day -> no send
        db.sms_compliance_profiles.update_one({"clinic_id": cid}, {"$set": {"quiet_days": [local.weekday()]}})
        db.reminder_settings.update_one({"clinic_id": cid}, {"$set": {"send_hour": 6, "last_run_date": None}})
        _fire()
        assert db.reminder_sends.count_documents({"item_id": it["id"]}) == 0, "sent on quiet day"
        # 3) already ran today -> no send
        db.sms_compliance_profiles.update_one({"clinic_id": cid}, {"$set": {"quiet_days": []}})
        db.reminder_settings.update_one({"clinic_id": cid}, {"$set": {"last_run_date": local.date().isoformat()}})
        _fire()
        assert db.reminder_sends.count_documents({"item_id": it["id"]}) == 0, "sent twice same day"
        # 4) eligible -> scheduled send logged
        db.reminder_settings.update_one({"clinic_id": cid}, {"$set": {"last_run_date": (local.date() - timedelta(days=1)).isoformat()}})
        _fire()
        s = db.reminder_sends.find_one({"item_id": it["id"]})
        assert s and s["trigger"] == "schedule" and s["stage"] == 0, s
        assert "is due today" in s["body"]
        assert db.reminder_settings.find_one({"clinic_id": cid})["last_run_date"] == local.date().isoformat()
    finally:
        db.sms_compliance_profiles.update_one({"clinic_id": cid}, {"$set": {"quiet_days": orig_qd}})
        db.reminder_settings.replace_one({"clinic_id": cid}, orig_settings or {"clinic_id": cid}, upsert=True)
        db.care_items.delete_one({"id": it["id"]})
        db.reminder_sends.delete_many({"item_id": it["id"]})
