# Seed/cleanup TEST_ UI data for iter11 frontend checks. Usage: python ui_seed_iter11.py seed|clean
import sys, uuid
from datetime import datetime, timezone, timedelta
from test_iter11_reminders_verify_results import db

cid = db.users.find_one({"email": "vet1@example.com"})["clinic_id"]
TAG = "TEST_iter11_ui"
if sys.argv[1] == "seed":
    owners = list(db.owners.find({"clinic_id": cid}).limit(2))
    sent_at = datetime.now(timezone.utc) - timedelta(days=3)
    phones = ["+14155559201", "+14155559202"]
    recs = [{"owner_id": o["id"], "name": o["name"], "phone_e164": phones[i], "body": "Hi", "status": "sent",
             "sent_at": sent_at.isoformat()} for i, o in enumerate(owners)]
    now = datetime.now(timezone.utc).isoformat()
    base = {"clinic_id": cid, "template_id": "x", "template_name": "TEST_t", "template_body": "Hi", "species": "all",
            "created_by": "owner2@example.com", "created_at": now, "tag": TAG}
    done_id, pend_id = str(uuid.uuid4()), str(uuid.uuid4())
    db.sms_campaigns.insert_many([
        {**base, "id": done_id, "name": "TEST_UI_done", "recipients": recs, "recipient_count": 2, "status": "completed",
         "completed_at": now, "approved_by": "vet1@example.com", "results": {"sent": 2, "blocked": 0, "failed": 0}},
        {**base, "id": pend_id, "name": "TEST_UI_pending", "recipients": [{**recs[0], "status": "pending", "sent_at": None}],
         "recipient_count": 1, "status": "pending_approval"}])
    pet = db.patients.find_one({"clinic_id": cid, "owner_id": owners[0]["id"]})["id"]
    db.receptionist_sessions.insert_one({"clinic_id": cid, "from_number": phones[0], "tag": TAG,
                                         "transcript": [{"role": "user", "text": "yes please", "at": (sent_at + timedelta(hours=2)).isoformat()}]})
    db.consent_events.insert_one({"clinic_id": cid, "phone_e164": phones[1], "consent_type": "marketing", "action": "opt_out",
                                  "at": (sent_at + timedelta(days=1)).isoformat(), "tag": TAG})
    db.appointments.insert_one({"id": TAG + "_a", "clinic_id": cid, "patient_id": pet, "tag": TAG,
                                "datetime": (sent_at + timedelta(days=2)).isoformat(), "created_at": "2020-01-01T00:00:00+00:00"})
    print(done_id, pend_id, owners[0]["id"], owners[1]["id"])
else:
    for coll in ("sms_campaigns", "receptionist_sessions", "consent_events", "appointments"):
        db[coll].delete_many({"tag": TAG})
    db.care_items.delete_many({"clinic_id": cid, "name": {"$regex": "^TEST_"}})
    print("cleaned")
