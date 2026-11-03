# Iter-12: billing paywall (402), Stripe webhook sync/dedupe, checkout/portal safety (503 + roles), billing cron auth
import hashlib
import hmac
import json
import os
import time
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests
from test_iter12_twilio_setup import BASE_URL, db, signup, login, H

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) pytest"}


def _env(key):
    for line in open("/app/backend/.env"):
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"')


WHSEC = _env("STRIPE_WEBHOOK_SECRET")
CRON = _env("WEBHOOK_CRON_SECRET")
ADMIN = _env("VETAURA_ADMIN_TOKEN")
EXPIRED_CID = "clinic_ba9f0696f489"


def send_event(etype, obj, eid=None, secret=WHSEC):
    eid = eid or f"evt_TEST_{uuid.uuid4().hex[:16]}"
    body = json.dumps({"id": eid, "object": "event", "type": etype, "data": {"object": obj}})
    ts = int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}.{body}".encode(), hashlib.sha256).hexdigest()
    r = requests.post(f"{BASE_URL}/api/stripe/webhook", data=body,
                      headers={**UA, "Content-Type": "application/json", "stripe-signature": f"t={ts},v1={sig}"})
    return r, eid


def sub(cid, status, sid="sub_TEST_1", **kw):
    now = int(time.time())
    o = {"id": sid, "object": "subscription", "status": status, "customer": "cus_TEST_1",
         "metadata": {"clinic_id": cid}, "cancel_at_period_end": False, "current_period_end": now + 30 * 86400}
    o.update(kw)
    return o


@pytest.fixture(scope="module")
def tc():
    """Throwaway owner clinic + reception user in it."""
    em, tok, cid, _ = signup("bill")
    em_r, tok_r, cid_r, _ = signup("billrec")
    db.users.update_one({"email": em_r}, {"$set": {"role": "reception", "clinic_id": cid}})
    yield {"tok": tok, "cid": cid, "rtok": tok_r}
    for c in (cid, cid_r):
        for coll in ("care_items", "patients", "owners", "visits", "labs", "weights", "appointments", "messages", "tasks", "clinics"):
            db[coll].delete_many({"clinic_id": c})
    db.users.delete_many({"email": {"$in": [em, em_r]}})
    db.stripe_events.delete_many({"_id": {"$regex": "^evt_TEST_"}})


# ---- Paywall ----
class TestPaywall:
    def test_expired_gated(self):
        t = login("expired@example.com")
        assert requests.get(f"{BASE_URL}/api/patients", headers={**UA, **H(t)}).status_code == 402
        assert requests.get(f"{BASE_URL}/api/clinic", headers={**UA, **H(t)}).status_code == 200
        me = requests.get(f"{BASE_URL}/api/auth/me", headers={**UA, **H(t)}).json()
        assert me["clinic"]["billing_access"] is False
        for p in ("/api/me/mobile", "/api/security/sessions"):
            r = requests.get(f"{BASE_URL}{p}", headers={**UA, **H(t)})
            print(p, r.status_code)
            assert r.status_code != 402

    def test_vet1_ok(self):
        t = login("vet1@example.com")
        assert requests.get(f"{BASE_URL}/api/patients", headers={**UA, **H(t)}).status_code == 200
        assert requests.get(f"{BASE_URL}/api/auth/me", headers={**UA, **H(t)}).json()["clinic"]["billing_access"] is True

    def test_access_rules_unit(self):
        import sys
        sys.path.insert(0, "/app/backend")
        os.environ.setdefault("JWT_SECRET", "x")
        from auth import clinic_has_access as f
        now = datetime.now(timezone.utc)
        fut, past = (now + timedelta(days=1)).isoformat(), (now - timedelta(days=1)).isoformat()
        assert f({"plan_status": "active"})
        assert f({"plan_status": "trialing", "trial_ends_at": fut})
        assert not f({"plan_status": "trialing", "trial_ends_at": past})
        assert f({"plan_status": "trialing", "trial_ends_at": past, "stripe_subscription_id": "sub_x"})
        assert f({"plan_status": "trial", "trial_ends_at": fut.replace("+00:00", "Z")})
        assert f({"plan_status": "past_due", "past_due_since": (now - timedelta(days=6)).isoformat()})
        assert not f({"plan_status": "past_due", "past_due_since": (now - timedelta(days=8)).isoformat()})
        for s in ("canceled", "unpaid", "incomplete", None):
            assert not f({"plan_status": s})


# ---- Webhook ----
class TestWebhook:
    def test_bad_signature(self):
        r, _ = send_event("customer.subscription.updated", {"id": "x"}, secret="whsec_wrong")
        assert r.status_code == 400
        r = requests.post(f"{BASE_URL}/api/stripe/webhook", data="{}", headers=UA)
        assert r.status_code == 400

    def test_sync_flow(self, tc):
        cid, tok = tc["cid"], tc["tok"]
        trial_end = int(time.time()) + 5 * 86400
        r, eid = send_event("customer.subscription.updated", sub(cid, "trialing", trial_end=trial_end))
        assert r.status_code == 200 and r.json()["status"] == "ok", r.text
        c = db.clinics.find_one({"clinic_id": cid})
        assert c["plan_status"] == "trialing" and c["stripe_subscription_id"] == "sub_TEST_1"
        assert c["stripe_customer_id"] == "cus_TEST_1" and c["current_period_end"] and c["cancel_at_period_end"] is False
        assert c["trial_ends_at"].startswith(datetime.fromtimestamp(trial_end, timezone.utc).date().isoformat())
        # duplicate
        r2, _ = send_event("customer.subscription.updated", sub(cid, "trialing"), eid=eid)
        assert r2.json()["status"] == "duplicate"
        # trial_will_end -> billing_notice
        r, _ = send_event("customer.subscription.trial_will_end", sub(cid, "trialing", trial_end=trial_end))
        assert r.status_code == 200
        assert "trial ends" in db.clinics.find_one({"clinic_id": cid}).get("billing_notice", "")
        # past_due set once
        send_event("customer.subscription.updated", sub(cid, "past_due"))
        first = db.clinics.find_one({"clinic_id": cid})["past_due_since"]
        time.sleep(1.1)
        send_event("customer.subscription.updated", sub(cid, "past_due", cancel_at_period_end=True))
        c = db.clinics.find_one({"clinic_id": cid})
        assert c["past_due_since"] == first and c["cancel_at_period_end"] is True
        assert requests.get(f"{BASE_URL}/api/patients", headers={**UA, **H(tok)}).status_code == 200
        # active clears
        send_event("customer.subscription.updated", sub(cid, "active"))
        c = db.clinics.find_one({"clinic_id": cid})
        assert c["plan_status"] == "active" and "past_due_since" not in c and "billing_notice" not in c
        # deleted -> canceled -> 402
        send_event("customer.subscription.deleted", sub(cid, "canceled"))
        assert db.clinics.find_one({"clinic_id": cid})["plan_status"] == "canceled"
        assert requests.get(f"{BASE_URL}/api/patients", headers={**UA, **H(tok)}).status_code == 402
        assert requests.get(f"{BASE_URL}/api/auth/me", headers={**UA, **H(tok)}).json()["clinic"]["billing_access"] is False

    def test_past_due_grace_expired(self, tc):
        cid, tok = tc["cid"], tc["tok"]
        db.clinics.update_one({"clinic_id": cid}, {"$set": {"plan_status": "past_due",
                              "past_due_since": (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()}})
        assert requests.get(f"{BASE_URL}/api/patients", headers={**UA, **H(tok)}).status_code == 402


# ---- Checkout / portal ----
class TestCheckoutPortal:
    def test_plans_503_not_500(self):
        r = requests.get(f"{BASE_URL}/api/plans", headers=UA)
        print("plans", r.status_code, r.text[:120])
        assert r.status_code in (200, 503)

    def test_checkout_owner_503(self, tc):
        db.clinics.update_one({"clinic_id": tc["cid"]}, {"$set": {"plan_status": "trialing", "stripe_subscription_id": None},
                                                         "$unset": {"past_due_since": ""}})
        r = requests.post(f"{BASE_URL}/api/payments/checkout", json={"lookup_key": "vetaura_starter_monthly",
                          "origin_url": "https://evil.example.com"}, headers={**UA, **H(tc["tok"])})
        print("checkout owner", r.status_code, r.text[:150])
        assert r.status_code == 503

    def test_checkout_non_owner_403(self, tc):
        for path, body in (("checkout", {"lookup_key": "vetaura_starter_monthly", "origin_url": "x"}),
                           ("checkout-bundle", {"core_lookup_key": "vetaura_starter_monthly", "origin_url": "x"})):
            r = requests.post(f"{BASE_URL}/api/payments/{path}", json=body, headers={**UA, **H(tc["rtok"])})
            print("non-owner", path, r.status_code, r.text[:120])
            assert r.status_code == 403, f"{path} non-owner got {r.status_code}"

    def test_checkout_double_sub_400(self, tc):
        db.clinics.update_one({"clinic_id": tc["cid"]}, {"$set": {"plan_status": "active", "stripe_subscription_id": "sub_TEST_1"}})
        r = requests.post(f"{BASE_URL}/api/payments/checkout", json={"lookup_key": "vetaura_starter_monthly",
                          "origin_url": "x"}, headers={**UA, **H(tc["tok"])})
        print("double sub", r.status_code, r.text[:120])
        assert r.status_code == 400, f"got {r.status_code}"

    def test_portal(self, tc):
        db.clinics.update_one({"clinic_id": tc["cid"]}, {"$set": {"stripe_customer_id": "cus_TEST_1"}})
        r = requests.post(f"{BASE_URL}/api/payments/portal", json={"origin_url": "x"}, headers={**UA, **H(tc["rtok"])})
        assert r.status_code == 403
        r = requests.post(f"{BASE_URL}/api/payments/portal", json={"origin_url": "x"}, headers={**UA, **H(tc["tok"])})
        print("portal owner", r.status_code, r.text[:200])
        assert r.status_code == 503, f"portal got {r.status_code}: {r.text[:200]}"


# ---- Cron ----
class TestCron:
    def test_close_auth(self):
        u = f"{BASE_URL}/api/billing-cycle/close"
        assert requests.post(u, headers=UA).status_code == 403
        assert requests.post(u, headers={**UA, "Authorization": "Bearer wrong"}).status_code == 403
        assert requests.post(u, headers={**UA, "X-Admin-Token": "wrong"}).status_code == 403
        r = requests.post(u, headers={**UA, "Authorization": f"Bearer {CRON}"})
        assert r.status_code == 200 and "count" in r.json(), r.text
        r = requests.post(u, headers={**UA, "X-Admin-Token": ADMIN})
        assert r.status_code == 200


def test_expired_clinic_state_intact():
    c = db.clinics.find_one({"clinic_id": EXPIRED_CID})
    assert c["plan_status"] == "trialing" and not c.get("stripe_subscription_id") and "past_due_since" not in c


def test_env_single_encryption_key():
    assert sum(1 for l in open("/app/backend/.env") if l.startswith("VETAURA_ENCRYPTION_KEY=")) == 1
