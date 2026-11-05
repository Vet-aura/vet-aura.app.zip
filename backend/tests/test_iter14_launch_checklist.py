# Iteration 14: LAUNCH_CHECKLIST end-to-end (owner / vet / front-desk) – backend side
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    for line in open("/app/frontend/.env"):
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip()
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"


def _admin_token():
    for line in open("/app/backend/.env"):
        if line.startswith("VETAURA_ADMIN_TOKEN="):
            return line.split("=", 1)[1].strip().strip('"')
    return None


TS = int(time.time())
S = {"owner_email": f"launch_owner_{TS}@example.com", "vet_email": f"launch_vet_{TS}@example.com",
     "fd_email": f"launch_frontdesk_{TS}@example.com", "pw": "LaunchTest!2026"}


def h(tok):
    return {"Authorization": f"Bearer {tok}"}


# ---------- Step 1: signup + onboarding + 4 sample patients
class TestStep1Signup:
    def test_signup_owner(self):
        r = requests.post(f"{API}/auth/signup", json={"email": S["owner_email"], "password": S["pw"],
                                                       "name": "Olivia Launch", "clinic_name": "TEST_Launch Clinic"})
        assert r.status_code == 200, r.text
        d = r.json()
        S["owner_tok"] = d["token"]; S["clinic_id"] = d["user"]["clinic_id"]
        assert d["user"]["role"] == "owner"
        open("/tmp/launch_state.txt", "w").write(f"{S['owner_email']}|{S['pw']}|{S['clinic_id']}\n")

    def test_onboard_and_patients(self):
        r = requests.patch(f"{API}/clinic", json={"onboarded": True}, headers=h(S["owner_tok"]))
        assert r.status_code == 200 and r.json()["onboarded"] is True
        p = requests.get(f"{API}/patients", headers=h(S["owner_tok"])).json()
        assert len(p) == 4
        S["patient_id"] = p[0]["id"]


# ---------- Step 2: scribe SOAP -> sign -> note under patient with signer's name
class TestStep2Scribe:
    def test_soap_and_sign(self):
        r = requests.post(f"{API}/scribe/soap", json={"transcript": "Owner reports dog vomiting twice since yesterday, still eating. Temp 38.9, mild abdominal discomfort. Plan bland diet, maropitant 1mg/kg SQ, recheck 48h.", "patient_id": S["patient_id"]}, headers=h(S["owner_tok"]), timeout=90)
        assert r.status_code == 200, r.text
        soap = r.json()
        for k in ("subjective", "objective", "assessment", "plan"):
            assert k in soap
        def as_text(v):
            return v if isinstance(v, str) else str(v)
        sv = requests.post(f"{API}/scribe/save", json={"patient_id": S["patient_id"], **{k: as_text(soap[k]) for k in ("subjective", "objective", "assessment", "plan")}}, headers=h(S["owner_tok"]))
        assert sv.status_code == 200, sv.text
        assert sv.json()["signed_by"] == "Olivia Launch"
        pd = requests.get(f"{API}/patients/{S['patient_id']}", headers=h(S["owner_tok"])).json()
        notes = pd.get("notes") or pd.get("soap_notes") or []
        assert any(n.get("signed_by") == "Olivia Launch" for n in notes), list(pd.keys())


# ---------- Step 3: differentials, discharge share, handoff, inbox draft->approve
class TestStep3Clinical:
    def test_differentials(self):
        r = requests.post(f"{API}/ai/differentials", json={"signalment": "5y MN Labrador", "complaint": "vomiting", "findings": "mild abdominal pain"}, headers=h(S["owner_tok"]), timeout=90)
        assert r.status_code == 200, r.text

    def test_discharge_share(self):
        r = requests.post(f"{API}/ai/discharge", json={"pet_name": "Biscuit", "plan_notes": "bland diet 3 days, maropitant", "share": True, "patient_id": S["patient_id"]}, headers=h(S["owner_tok"]), timeout=90)
        assert r.status_code == 200, r.text
        d = r.json()
        tok = d.get("share_token") or d.get("token")
        assert tok, d.keys()
        S["share_token"] = tok
        open("/tmp/launch_share.txt", "w").write(tok)
        pub = requests.get(f"{API}/discharge/public/{tok}")
        assert pub.status_code == 200

    def test_handoff(self):
        r = requests.post(f"{API}/ai/handoff", json={}, headers=h(S["owner_tok"]), timeout=90)
        assert r.status_code == 200, r.text

    def test_inbox_draft_approve(self):
        msgs = requests.get(f"{API}/messages", headers=h(S["owner_tok"])).json()
        assert len(msgs) > 0
        mid = msgs[0]["id"]
        d = requests.post(f"{API}/messages/{mid}/draft", headers=h(S["owner_tok"]), timeout=90)
        assert d.status_code == 200, d.text
        a = requests.post(f"{API}/messages/{mid}/approve", headers=h(S["owner_tok"]))
        assert a.status_code == 200, a.text
        m2 = [m for m in requests.get(f"{API}/messages", headers=h(S["owner_tok"])).json() if m["id"] == mid][0]
        assert m2["status"] == "sent"


# ---------- Step 4: follow-ups auto-generate + care gaps
class TestStep4:
    def test_tasks_autogen(self):
        r = requests.post(f"{API}/tasks/auto-generate", headers=h(S["owner_tok"]))
        assert r.status_code == 200, r.text
        t = requests.get(f"{API}/tasks", headers=h(S["owner_tok"])).json()
        assert len(t) > 0

    def test_care_gaps(self):
        r = requests.get(f"{API}/care-gaps", headers=h(S["owner_tok"]))
        assert r.status_code == 200
        print("care-gaps:", str(r.json())[:300])


# ---------- Step 5: team invites + role-based access
class TestStep5Team:
    def test_invite_and_accept(self):
        for key, role, name in (("vet", "vet", "Victor Vetson"), ("fd", "reception", "Fiona Desk")):
            r = requests.post(f"{API}/team/invitations", json={"email": S[f"{key}_email"], "role": role, "name": name}, headers=h(S["owner_tok"]))
            assert r.status_code == 200, r.text
            inv = r.json()
            token = inv.get("token") or (inv.get("invitation") or {}).get("token")
            assert token, inv
            peek = requests.get(f"{API}/invitations/{token}")
            assert peek.status_code == 200 and peek.json()["role"] == role
            su = requests.post(f"{API}/auth/signup", json={"email": S[f"{key}_email"], "password": S["pw"], "name": name, "invite_token": token})
            assert su.status_code == 200, su.text
            assert su.json()["user"]["clinic_id"] == S["clinic_id"] and su.json()["user"]["role"] == role
            lg = requests.post(f"{API}/auth/login", json={"email": S[f"{key}_email"], "password": S["pw"]})
            assert lg.status_code == 200
            S[f"{key}_tok"] = lg.json()["token"]
        mem = requests.get(f"{API}/team/members", headers=h(S["owner_tok"])).json()
        assert len(mem) == 3

    @pytest.mark.parametrize("who", ["vet", "fd"])
    def test_owner_only_endpoints_forbidden(self, who):
        tok = S[f"{who}_tok"]
        res = {
            "invite": requests.post(f"{API}/team/invitations", json={"email": f"x{TS}@example.com", "role": "vet"}, headers=h(tok)).status_code,
            "checkout": requests.post(f"{API}/payments/checkout", json={"lookup_key": "starter", "origin_url": BASE_URL}, headers=h(tok)).status_code,
            "portal": requests.post(f"{API}/payments/portal", json={"origin_url": BASE_URL}, headers=h(tok)).status_code,
            "mkt_template": requests.post(f"{API}/sms/marketing/templates", json={"name": "x", "body": "hi"}, headers=h(tok)).status_code,
        }
        print(who, res)
        assert all(v == 403 for v in res.values()), res

    def test_frontdesk_cannot_patch_clinic(self):
        r = requests.patch(f"{API}/clinic", json={"name": "TEST_Launch Clinic"}, headers=h(S["fd_tok"]))
        print("frontdesk PATCH /clinic ->", r.status_code)
        assert r.status_code == 403

    def test_frontdesk_cannot_sign_soap(self):
        r = requests.post(f"{API}/scribe/save", json={"patient_id": S["patient_id"], "subjective": "s", "objective": "o", "assessment": "a", "plan": "p"}, headers=h(S["fd_tok"]))
        print("frontdesk sign SOAP ->", r.status_code)
        assert r.status_code == 403


# ---------- Step 7: marketing single-owner self-approve; two-owner rule
class TestStep7Marketing:
    def test_single_owner_self_approve(self):
        t = requests.post(f"{API}/sms/marketing/templates", json={"name": "TEST_launch", "body": "Hi {first_name}, {pet_name} is due!"}, headers=h(S["owner_tok"]))
        assert t.status_code == 200, t.text
        tid = t.json()["id"]
        c = requests.post(f"{API}/sms/marketing/campaigns", json={"template_id": tid, "name": "TEST_launch blast"}, headers=h(S["owner_tok"]))
        print("campaign create:", c.status_code, c.text[:200])
        if c.status_code != 200:
            pytest.skip(f"campaign create blocked: {c.text[:150]}")
        cid = c.json()["id"]
        a = requests.post(f"{API}/sms/marketing/campaigns/{cid}/approve", headers=h(S["owner_tok"]))
        print("self-approve:", a.status_code, a.text[:200])
        assert a.status_code != 403, "single-owner self approval blocked by two-person rule"
        assert a.status_code in (200, 400)

    def test_two_owner_rule(self):
        lg = requests.post(f"{API}/auth/login", json={"email": "vet1@example.com", "password": "strongpass123"})
        assert lg.status_code == 200
        tok = lg.json()["token"]
        tpls = requests.get(f"{API}/sms/marketing/templates", headers=h(tok)).json()
        if not tpls:
            pytest.skip("no templates for vet1")
        tid = (tpls[0] if isinstance(tpls, list) else tpls["templates"][0])["id"]
        c = requests.post(f"{API}/sms/marketing/campaigns", json={"template_id": tid, "name": "TEST_iter14 two-person"}, headers=h(tok))
        if c.status_code != 200:
            pytest.skip(f"campaign create blocked: {c.text[:150]}")
        cid = c.json()["id"]
        a = requests.post(f"{API}/sms/marketing/campaigns/{cid}/approve", headers=h(tok))
        requests.post(f"{API}/sms/marketing/campaigns/{cid}/cancel", headers=h(tok))
        assert a.status_code == 403 and "two-person" in a.text


# ---------- Step 8: demo lead + admin leads
class TestStep8Leads:
    def test_demo_and_admin_leads(self):
        email = f"launch_lead_{TS}@example.com"
        r = requests.post(f"{API}/marketing/demo", json={"name": "TEST_Lead", "email": email, "clinic": "TEST_Lead Clinic", "message": "hi"})
        assert r.status_code == 200 and r.json()["ok"]
        assert requests.get(f"{API}/admin/leads").status_code == 403
        assert requests.get(f"{API}/admin/leads", headers={"X-Admin-Token": "wrong"}).status_code == 403
        ok = requests.get(f"{API}/admin/leads", headers={"X-Admin-Token": _admin_token()})
        assert ok.status_code == 200
        assert any(d.get("email") == email for d in ok.json()["demo_requests"])


# ---------- Cost guard (runs last)
class TestZCostGuard:
    def test_tryit_limit(self):
        codes = [requests.post(f"{API}/marketing/try-it", json={"url": "http://127.0.0.1/"}).status_code for _ in range(6)]
        print("try-it codes:", codes)
        assert codes[:5] == [400] * 5 and codes[5] == 429

    def test_receptionist_chat_limit(self):
        # disable receptionist for test clinic so calls don't hit the LLM (limiter runs first)
        requests.patch(f"{API}/receptionist/config", json={"enabled": False}, headers=h(S["owner_tok"]))
        sid = uuid.uuid4().hex
        # NOTE: preview egress may alternate between 2 NAT IPs, so loop until a 429 (max 70)
        codes = []
        for _ in range(70):
            c = requests.post(f"{API}/receptionist/chat", json={"clinic_id": S["clinic_id"], "session_id": sid, "message": "hi"}).status_code
            codes.append(c)
            if c == 429:
                break
        print("chat calls until 429:", len(codes), set(codes[:-1]))
        assert codes[-1] == 429 and len(codes) >= 31
