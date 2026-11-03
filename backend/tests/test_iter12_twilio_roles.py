# Iter-12: role enforcement on Twilio connect/rotate/disconnect (non-owner must get 403)
import uuid
import requests
from test_iter12_twilio_setup import BASE_URL, db, signup, H, FAKE

T = f"{BASE_URL}/api/integrations/twilio"


def test_non_owner_cannot_mutate_twilio_creds():
    em_o, tok_o, cid, _ = signup("roleown")
    em_r, tok_r, own_cid, _ = signup("rolerec")
    db.users.update_one({"email": em_r}, {"$set": {"role": "reception", "clinic_id": cid}})
    db.twilio_credentials.insert_one({"clinic_id": cid, "account_sid": FAKE["account_sid"], "api_key_sid": FAKE["api_key_sid"],
                                      "api_key_secret_encrypted": "", "webhook_token": "TEST_tok_" + uuid.uuid4().hex})
    try:
        h = H(tok_r)
        g = requests.get(T, headers=h).json()
        print("reception GET sees webhook_token:", "webhook_token" in g and bool(g.get("webhook_token")))
        rot = requests.post(f"{T}/rotate-webhook-token", headers=h)
        save = requests.post(T, json=FAKE, headers=h)
        dele = requests.delete(T, headers=h)
        print("rotate", rot.status_code, "save", save.status_code, "delete", dele.status_code)
        assert rot.status_code == 403, f"rotate by reception returned {rot.status_code}"
        assert dele.status_code == 403, f"delete by reception returned {dele.status_code}"
        assert save.status_code == 403, f"save by reception returned {save.status_code}"
    finally:
        db.twilio_credentials.delete_many({"clinic_id": cid})
        for c in (cid, own_cid):
            for coll in ("care_items", "patients", "owners", "clinics", "twilio_setup"):
                db[coll].delete_many({"clinic_id": c})
        db.users.delete_many({"email": {"$in": [em_o, em_r]}})
