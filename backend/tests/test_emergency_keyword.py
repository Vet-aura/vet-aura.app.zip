"""Verify emergency-keyword safety net by injecting message body directly."""
import os, time, uuid, requests, asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or "https://pet-care-helper-1.preview.emergentagent.com"
API = f"{BASE_URL}/api"
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


def test_emergency_keyword_forces_urgent():
    # Signup fresh account
    s = requests.Session()
    email = f"TEST_emerg_{int(time.time())}_{uuid.uuid4().hex[:6]}@example.com"
    r = s.post(f"{API}/auth/signup", json={
        "email": email, "password": "strongpass123",
        "name": "Emerg Vet", "clinic_name": "TEST Emerg"
    })
    assert r.status_code == 200, r.text
    tok = r.json()["token"]
    cid = r.json()["user"]["clinic_id"]

    # Inject an emergency message into DB directly
    async def _inject():
        client = AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]
        pats = await db.patients.find({"clinic_id": cid}).to_list(10)
        assert pats, "no patients seeded"
        owner = await db.owners.find_one({"clinic_id": cid})
        mid = str(uuid.uuid4())
        await db.messages.insert_one({
            "id": mid, "clinic_id": cid,
            "owner_id": owner["id"], "patient_id": pats[0]["id"],
            "received_at": "2026-01-01T00:00:00+00:00",
            "channel": "SMS", "subject": "URGENT",
            "body": "Bella suddenly collapsed and then had a seizure this morning, she is not responding well",
            "status": "new", "category": None, "draft": None,
        })
        client.close()
        return mid

    mid = asyncio.get_event_loop().run_until_complete(_inject())

    # Now call draft — should force urgent_review + create urgent task
    tasks_before = len(s.get(f"{API}/tasks", headers={"Authorization": f"Bearer {tok}"}).json())
    r2 = s.post(f"{API}/messages/{mid}/draft", headers={"Authorization": f"Bearer {tok}"})
    assert r2.status_code == 200, r2.text
    d = r2.json()
    assert d["category"] == "urgent_review", f"expected urgent_review, got {d.get('category')}"
    assert "[EMERGENCY KEYWORD DETECTED:" in (d.get("internal_note") or ""), f"missing emergency prefix in internal_note: {d.get('internal_note')}"
    # Priority=urgent task created
    tasks_after = s.get(f"{API}/tasks", headers={"Authorization": f"Bearer {tok}"}).json()
    assert len(tasks_after) == tasks_before + 1
    urgent = [t for t in tasks_after if t.get("priority") == "urgent" and t.get("source_id") == mid]
    assert urgent, "expected urgent-priority task tied to emergency message"
