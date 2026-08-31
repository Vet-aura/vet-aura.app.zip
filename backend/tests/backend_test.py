"""Vetaura SaaS backend tests — auth, multi-tenant isolation, AI, Stripe plans, exports, audit, public discharge."""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or "https://pet-care-helper-1.preview.emergentagent.com"
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"

TS = int(time.time())


def _rand_email(tag="a"):
    return f"TEST_{tag}_{TS}_{uuid.uuid4().hex[:6]}@example.com"


# --------- fixtures ---------
@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def account_a(sess):
    email = _rand_email("A")
    r = sess.post(f"{API}/auth/signup", json={
        "email": email, "password": "strongpass123",
        "name": "Alice Vet", "clinic_name": "TEST Clinic A"
    })
    assert r.status_code == 200, r.text
    d = r.json()
    return {"email": email, "password": "strongpass123", "token": d["token"], "user": d["user"], "clinic": d["user"]["clinic"]}


@pytest.fixture(scope="module")
def account_b(sess):
    email = _rand_email("B")
    r = sess.post(f"{API}/auth/signup", json={
        "email": email, "password": "strongpass123",
        "name": "Bob Vet", "clinic_name": "TEST Clinic B"
    })
    assert r.status_code == 200, r.text
    d = r.json()
    return {"email": email, "password": "strongpass123", "token": d["token"], "user": d["user"], "clinic": d["user"]["clinic"]}


def h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# --------- Basic ---------
class TestBasics:
    def test_root(self, sess):
        r = sess.get(f"{API}/")
        assert r.status_code == 200
        assert r.json().get("service") == "Vetaura"


# --------- Auth ---------
class TestAuth:
    def test_signup_creates_user_clinic_and_seeds(self, account_a):
        u = account_a["user"]
        c = account_a["clinic"]
        assert u["email"].startswith("test_a_") or "TEST_A" in u["email"].upper()
        assert c["plan"] == "trial"
        assert c["plan_status"] == "trialing"
        assert c["onboarded"] is False
        assert account_a["token"]

    def test_signup_duplicate_rejected(self, sess, account_a):
        r = sess.post(f"{API}/auth/signup", json={
            "email": account_a["email"], "password": "strongpass123",
            "name": "Dup", "clinic_name": "Dup"
        })
        assert r.status_code == 400

    def test_login_success(self, sess, account_a):
        r = sess.post(f"{API}/auth/login", json={"email": account_a["email"], "password": "strongpass123"})
        assert r.status_code == 200
        assert r.json().get("token")

    def test_login_wrong_password(self, sess, account_a):
        r = sess.post(f"{API}/auth/login", json={"email": account_a["email"], "password": "wrong-pass"})
        assert r.status_code == 401

    def test_me_with_bearer(self, sess, account_a):
        r = sess.get(f"{API}/auth/me", headers=h(account_a["token"]))
        assert r.status_code == 200
        d = r.json()
        assert d["email"].lower() == account_a["email"].lower()
        assert d["clinic"]["clinic_id"] == account_a["clinic"]["clinic_id"]

    def test_me_without_token_401(self, sess):
        r = sess.get(f"{API}/auth/me")
        assert r.status_code == 401


# --------- Multi-tenant isolation ---------
class TestTenantIsolation:
    def test_each_clinic_has_only_4_seeded_patients(self, sess, account_a, account_b):
        ra = sess.get(f"{API}/patients", headers=h(account_a["token"]))
        rb = sess.get(f"{API}/patients", headers=h(account_b["token"]))
        assert ra.status_code == 200 and rb.status_code == 200
        pa = ra.json(); pb = rb.json()
        assert len(pa) == 4, f"Account A: expected 4 patients, got {len(pa)}"
        assert len(pb) == 4, f"Account B: expected 4 patients, got {len(pb)}"
        a_ids = {p["id"] for p in pa}
        b_ids = {p["id"] for p in pb}
        assert a_ids.isdisjoint(b_ids), "Cross-tenant leak: patients shared between clinics"

    def test_stats_scoped(self, sess, account_a):
        r = sess.get(f"{API}/stats", headers=h(account_a["token"]))
        assert r.status_code == 200
        d = r.json()
        assert d["patients"] == 4


# --------- Scribe / AI ---------
class TestScribe:
    def test_soap_requires_auth(self, sess):
        r = sess.post(f"{API}/scribe/soap", json={"transcript": "test"})
        assert r.status_code == 401

    def test_soap_with_token(self, sess, account_a):
        r = sess.post(f"{API}/scribe/soap", headers=h(account_a["token"]),
                      json={"transcript": "6yo Labrador with vomiting for 2 days. Physical exam normal, mild dehydration."})
        assert r.status_code == 200
        d = r.json()
        for key in ("subjective", "objective", "assessment", "plan"):
            assert key in d and d[key]

    def test_scribe_save_records_signed_by(self, sess, account_a):
        pats = sess.get(f"{API}/patients", headers=h(account_a["token"])).json()
        pid = pats[0]["id"]
        r = sess.post(f"{API}/scribe/save", headers=h(account_a["token"]), json={
            "patient_id": pid, "subjective": "S", "objective": "O", "assessment": "A", "plan": "P"
        })
        assert r.status_code == 200
        d = r.json()
        assert d["signed_by"] == account_a["user"]["name"]
        # verify in patient detail
        pd = sess.get(f"{API}/patients/{pid}", headers=h(account_a["token"])).json()
        assert any(n["id"] == d["id"] for n in pd["soap_notes"])


# --------- Discharge & public share ---------
class TestDischargeShare:
    def test_share_creates_token_and_public_returns_branding(self, sess, account_a):
        # First set clinic branding
        sess.patch(f"{API}/clinic", headers=h(account_a["token"]), json={
            "name": "TEST Clinic A Renamed",
            "primary_color": "#112233",
            "discharge_footer": "Call us anytime",
            "onboarded": True,
        })
        r = sess.post(f"{API}/ai/discharge", headers=h(account_a["token"]), json={
            "pet_name": "Bella", "plan_notes": "rest, meds x7 days", "language": "English", "share": True
        })
        assert r.status_code == 200
        d = r.json()
        token = d.get("share_token")
        assert token, f"expected share_token; got: {list(d)}"

        # Public — no auth
        pub = requests.get(f"{API}/discharge/public/{token}")
        assert pub.status_code == 200
        pd = pub.json()
        assert pd["clinic_name"] == "TEST Clinic A Renamed"
        assert pd["primary_color"] == "#112233"
        assert pd["footer"] == "Call us anytime"
        assert "content" in pd
        # medications/warning_signs should be in content
        content = pd["content"]
        assert isinstance(content, dict)


# --------- Clinic settings ---------
class TestClinic:
    def test_patch_clinic_persists(self, sess, account_b):
        r = sess.patch(f"{API}/clinic", headers=h(account_b["token"]), json={
            "name": "TEST Clinic B v2", "primary_color": "#ff5500", "onboarded": True
        })
        assert r.status_code == 200
        d = r.json()
        assert d["name"] == "TEST Clinic B v2"
        assert d["primary_color"] == "#ff5500"
        assert d["onboarded"] is True


# --------- Audit ---------
class TestAudit:
    def test_audit_has_entries(self, sess, account_a):
        r = sess.get(f"{API}/audit", headers=h(account_a["token"]))
        assert r.status_code == 200
        items = r.json()
        actions = {i["action"] for i in items}
        # We expect at least soap/discharge/clinic actions from prior tests
        assert "soap_signed" in actions
        assert "discharge_shared" in actions
        assert "clinic_updated" in actions


# --------- CSV exports ---------
class TestCSV:
    def test_patients_csv(self, sess, account_a):
        r = sess.get(f"{API}/export/patients.csv", headers={"Authorization": f"Bearer {account_a['token']}"})
        assert r.status_code == 200
        assert "Name,Species,Breed" in r.text
        lines = [l for l in r.text.strip().split("\n") if l]
        assert len(lines) >= 5  # header + 4 rows

    def test_notes_csv(self, sess, account_a):
        r = sess.get(f"{API}/export/notes.csv", headers={"Authorization": f"Bearer {account_a['token']}"})
        assert r.status_code == 200
        assert "Date,Patient,Signed by" in r.text


# --------- Stripe plans / checkout / marketing demo ---------
class TestStripe:
    def test_plans_public(self, sess):
        r = sess.get(f"{API}/plans")
        assert r.status_code == 200
        plans = r.json().get("plans", [])
        keys = {p["lookup_key"] for p in plans}
        assert {"vetaura_solo_monthly", "vetaura_clinic_monthly", "vetaura_multisite_monthly"}.issubset(keys)
        by_key = {p["lookup_key"]: p for p in plans}
        assert by_key["vetaura_solo_monthly"]["amount"] == 4900
        assert by_key["vetaura_clinic_monthly"]["amount"] == 19900
        assert by_key["vetaura_multisite_monthly"]["amount"] == 49900
        for p in plans:
            assert p.get("trial_period_days") == 14

    def test_checkout_returns_stripe_url(self, sess, account_a):
        r = sess.post(f"{API}/payments/checkout", headers=h(account_a["token"]), json={
            "lookup_key": "vetaura_solo_monthly",
            "origin_url": BASE_URL,
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert "checkout_url" in d
        assert "stripe.com" in d["checkout_url"]


class TestMarketing:
    def test_demo_request(self, sess):
        r = sess.post(f"{API}/marketing/demo", json={
            "name": "TEST Demo", "email": _rand_email("demo"),
            "clinic": "TEST Clinic", "message": "Need a demo"
        })
        assert r.status_code == 200
        assert r.json().get("ok") is True
