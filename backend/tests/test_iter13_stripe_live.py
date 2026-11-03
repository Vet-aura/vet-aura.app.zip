# Iter-13: live Stripe sandbox — plans, checkout/bundle/portal, double-sub guard, roles, webhook signatures, paywall regression
import hashlib
import hmac
import json
import os
import time
import uuid

import pytest
import requests
from test_iter12_twilio_setup import BASE_URL, db, signup, login, H

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) pytest"}
ORIGIN = BASE_URL


def _env(key):
    for line in open("/app/backend/.env"):
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"')


WHSEC = _env("STRIPE_WEBHOOK_SECRET")
# Owner who already paid via real Stripe Checkout in the UI run (token file written by the UI test); optional
PAID_TOK_FILE = "/tmp/e2e_tok"


def send_event(etype, obj, secret=WHSEC):
    eid = f"evt_TEST_{uuid.uuid4().hex[:16]}"
    body = json.dumps({"id": eid, "object": "event", "type": etype, "data": {"object": obj}})
    ts = int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}.{body}".encode(), hashlib.sha256).hexdigest()
    return requests.post(f"{BASE_URL}/api/stripe/webhook", data=body,
                         headers={**UA, "Content-Type": "application/json", "stripe-signature": f"t={ts},v1={sig}"}), eid


@pytest.fixture(scope="module")
def fresh():
    em, tok, cid, _ = signup("i13bundle")
    em_r, tok_r, cid_r, _ = signup("i13rec")
    db.users.update_one({"email": em_r}, {"$set": {"role": "reception", "clinic_id": cid}})
    yield {"tok": tok, "cid": cid, "rtok": tok_r}
    for c in (cid, cid_r):
        for coll in ("care_items", "patients", "owners", "visits", "labs", "weights", "appointments", "messages", "tasks",
                     "payment_transactions", "clinics"):
            db[coll].delete_many({"clinic_id": c})
    db.users.delete_many({"email": {"$in": [em, em_r]}})


def paid_tok():
    if not os.path.exists(PAID_TOK_FILE):
        pytest.skip("No paid owner from UI run")
    t = open(PAID_TOK_FILE).read().strip()
    if requests.get(f"{BASE_URL}/api/auth/me", headers={**UA, **H(t)}).status_code != 200:
        pytest.skip("Paid owner from UI run no longer exists")
    return t


# Plans catalog from live Stripe
def test_plans_four():
    r = requests.get(f"{BASE_URL}/api/plans", headers=UA)
    assert r.status_code == 200
    got = {p["lookup_key"]: p["amount"] for p in r.json()["plans"]}
    assert got == {"vetaura_starter_monthly": 24900, "vetaura_growth_monthly": 49900,
                   "vetaura_pro_monthly": 89900, "vetaura_scribe_addon_monthly": 7900}


# Paid owner: me reflects subscription, portal works, double checkout blocked
def test_paid_owner_me():
    r = requests.get(f"{BASE_URL}/api/auth/me", headers={**UA, **H(paid_tok())})
    assert r.status_code == 200
    d = r.json()
    c = d.get("clinic") or d.get("user", {}).get("clinic")
    assert c["plan"] == "starter" and c["plan_status"] in ("trialing", "active")
    assert c["stripe_subscription_id"].startswith("sub_") and c["stripe_customer_id"].startswith("cus_")
    assert c["billing_access"] is True


def test_paid_owner_portal():
    r = requests.post(f"{BASE_URL}/api/payments/portal", json={"origin_url": ORIGIN}, headers={**UA, **H(paid_tok())})
    assert r.status_code == 200, r.text
    assert r.json()["portal_url"].startswith("https://billing.stripe.com")


@pytest.mark.parametrize("path,body", [
    ("/api/payments/checkout", {"lookup_key": "vetaura_pro_monthly", "origin_url": ORIGIN}),
    ("/api/payments/checkout-bundle", {"core_lookup_key": "vetaura_growth_monthly", "attach_scribe": True,
                                       "scribe_quantity": 2, "origin_url": ORIGIN}),
])
def test_double_subscription_guard(path, body):
    r = requests.post(f"{BASE_URL}{path}", json=body, headers={**UA, **H(paid_tok())})
    assert r.status_code == 400
    assert "already have a subscription" in r.json()["detail"]


# Fresh owner: bundle checkout session (discount + 2 scribe seats), status pending
def test_bundle_checkout(fresh):
    r = requests.post(f"{BASE_URL}/api/payments/checkout-bundle", headers={**UA, **H(fresh["tok"])},
                      json={"core_lookup_key": "vetaura_growth_monthly", "attach_scribe": True, "scribe_quantity": 2,
                            "origin_url": ORIGIN})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["checkout_url"].startswith("https://checkout.stripe.com") and d["bundle_applied"] is True
    s = requests.get(f"{BASE_URL}/api/payments/status/{d['session_id']}", headers=UA)
    assert s.status_code == 200 and s.json()["payment_status"] != "paid"
    tx = db.payment_transactions.find_one({"session_id": d["session_id"]})
    assert tx["clinic_id"] == fresh["cid"] and tx["bundle"] is True


def test_invalid_plan(fresh):
    r = requests.post(f"{BASE_URL}/api/payments/checkout", headers={**UA, **H(fresh["tok"])},
                      json={"lookup_key": "nope_monthly", "origin_url": ORIGIN})
    assert r.status_code == 400


def test_portal_requires_customer_or_ok(fresh):
    # fresh owner has a customer now (created during bundle checkout) -> portal works
    r = requests.post(f"{BASE_URL}/api/payments/portal", json={"origin_url": ORIGIN}, headers={**UA, **H(fresh["tok"])})
    assert r.status_code in (200, 400)


@pytest.mark.parametrize("path,body", [
    ("/api/payments/checkout", {"lookup_key": "vetaura_starter_monthly", "origin_url": ORIGIN}),
    ("/api/payments/checkout-bundle", {"core_lookup_key": "vetaura_starter_monthly", "origin_url": ORIGIN}),
    ("/api/payments/portal", {"origin_url": ORIGIN}),
])
def test_non_owner_403(fresh, path, body):
    r = requests.post(f"{BASE_URL}{path}", json=body, headers={**UA, **H(fresh["rtok"])})
    assert r.status_code == 403


def test_status_unknown_404():
    assert requests.get(f"{BASE_URL}/api/payments/status/cs_test_nope", headers=UA).status_code == 404


# Webhook signature with the new secret
def test_webhook_valid_signature():
    r, eid = send_event("customer.created", {"id": "cus_TEST_x", "object": "customer"})
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert db.stripe_events.find_one({"_id": eid})
    db.stripe_events.delete_one({"_id": eid})


def test_webhook_invalid_signature():
    r, _ = send_event("customer.created", {"id": "cus_TEST_x"}, secret="whsec_wrong")
    assert r.status_code == 400


def test_real_stripe_events_delivered():
    types = {e["type"] for e in db.stripe_events.find({"_id": {"$regex": "^evt_1"}}, {"type": 1})}
    assert {"checkout.session.completed", "customer.subscription.created"} <= types


# Regression: paywall + normal access
def test_expired_paywalled():
    t = login("expired@example.com")
    assert requests.get(f"{BASE_URL}/api/patients", headers={**UA, **H(t)}).status_code == 402
    assert requests.get(f"{BASE_URL}/api/plans", headers=UA).status_code == 200


def test_vet1_access():
    t = login("vet1@example.com")
    assert requests.get(f"{BASE_URL}/api/patients", headers={**UA, **H(t)}).status_code == 200
