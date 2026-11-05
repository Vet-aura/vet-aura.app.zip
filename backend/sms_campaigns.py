"""Marketing bulk SMS: locked templates, marketing-consent audience, two-person approval, quiet-hours queue."""
from __future__ import annotations
import asyncio
import hmac
import logging
import os
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from motor.motor_asyncio import AsyncIOMotorDatabase
from sms_compliance import _normalize_phone, _in_quiet_hours, next_send_window, can_send_sms
from credentials_service import get_twilio_creds, get_twilio_client_from_creds
from sms_sender import send_raw_sms

logger = logging.getLogger(__name__)
MERGE_FIELDS = {"first_name", "pet_name", "clinic_name"}
OPT_OUT_SUFFIX = " Reply STOP to opt out."
STALE_SENDING = timedelta(minutes=10)
TEST_LIMIT_PER_CAMPAIGN = 5
REPLY_WINDOW = timedelta(days=7)
BOOKING_WINDOW = timedelta(days=30)


def _ts(v) -> Optional[datetime]:
    """Parse ISO strings ('Z' or offset) / datetimes into aware UTC datetimes; None if unparseable."""
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TemplateReq(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    body: str = Field(min_length=1, max_length=480)

    @field_validator("body")
    @classmethod
    def _fields(cls, v):
        bad = set(re.findall(r"\{(\w+)\}", v)) - MERGE_FIELDS
        if bad:
            raise ValueError(f"Unsupported merge field(s): {', '.join(sorted(bad))}. Allowed: first_name, pet_name, clinic_name")
        return v.strip()


class AudienceReq(BaseModel):
    template_id: str
    species: Optional[str] = None


class CampaignReq(AudienceReq):
    name: str = Field(min_length=1, max_length=120)


class RejectReq(BaseModel):
    reason: str = Field(default="", max_length=300)


def render(body: str, ctx: dict) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: str(ctx.get(m.group(1), "")), body)


def final_body(template_body: str, ctx: dict) -> str:
    """Exact text that is sent: rendered template, clinic identity (if not already merged) and STOP line."""
    text = render(template_body, ctx).rstrip()
    if "{clinic_name}" not in template_body and ctx.get("clinic_name"):
        text += f" — {ctx['clinic_name']}."
    return text + OPT_OUT_SUFFIX


def _require_owner(user: dict, action: str):
    if user.get("role", "owner") != "owner":
        raise HTTPException(403, f"Only clinic owners can {action}.")


def build_campaign_routes(db: AsyncIOMotorDatabase, auth_dep):
    router = APIRouter(prefix="/api/sms/marketing")

    async def _template(cid: str, tid: str) -> dict:
        t = await db.sms_marketing_templates.find_one({"id": tid, "clinic_id": cid, "status": "active"}, {"_id": 0})
        if not t:
            raise HTTPException(404, "Template not found or archived")
        return t

    async def _audience(cid: str, template: dict, species: Optional[str]) -> dict:
        clinic = await db.clinics.find_one({"clinic_id": cid}, {"_id": 0, "name": 1}) or {}
        owners = await db.owners.find({"clinic_id": cid}, {"_id": 0}).to_list(5000)
        pq = {"clinic_id": cid}
        if species and species != "all":
            pq["species"] = species
        pets: dict[str, list[str]] = {}
        for p in await db.patients.find(pq, {"_id": 0, "owner_id": 1, "name": 1}).to_list(10000):
            pets.setdefault(p.get("owner_id"), []).append(p["name"])
        consent = {r["phone_e164"]: r["status"] for r in await db.consent_records.find(
            {"clinic_id": cid, "consent_type": "marketing"}, {"_id": 0}).to_list(10000)}
        eligible, excluded, seen = [], {"no_phone": 0, "no_consent": 0, "opted_out": 0, "duplicate": 0}, set()
        for o in owners:
            if o["id"] not in pets:
                continue
            phone = _normalize_phone(o.get("phone", ""))
            if len(phone) < 8:
                excluded["no_phone"] += 1
            elif phone in seen:
                excluded["duplicate"] += 1
            elif consent.get(phone) == "opted_out":
                excluded["opted_out"] += 1
            elif consent.get(phone) != "opted_in":
                excluded["no_consent"] += 1
            else:
                seen.add(phone)
                ctx = {"first_name": (o.get("name") or "").split(" ")[0], "pet_name": pets[o["id"]][0],
                       "clinic_name": clinic.get("name", "")}
                eligible.append({"owner_id": o["id"], "name": o.get("name", ""), "phone_e164": phone,
                                 "body": final_body(template["body"], ctx), "status": "pending"})
        return {"eligible": eligible, "excluded": excluded}

    async def _readiness_reason(cid: str) -> str:
        profile = await db.sms_compliance_profiles.find_one({"clinic_id": cid}) or {}
        if profile.get("brand_status") != "approved" or profile.get("campaign_status") != "approved":
            return "Brand and Campaign must be approved in SMS Compliance before marketing can send."
        creds = await db.twilio_credentials.find_one({"clinic_id": cid})
        if not creds or not creds.get("messaging_service_sid"):
            return "Connect a Twilio Messaging Service before sending marketing."
        return ""

    async def dispatch(campaign_id: str):
        camp = await db.sms_campaigns.find_one({"id": campaign_id}, {"_id": 0})
        if not camp or camp["status"] != "sending":
            return
        cid = camp["clinic_id"]
        profile = await db.sms_compliance_profiles.find_one({"clinic_id": cid}) or {}
        if _in_quiet_hours(profile):
            nxt = next_send_window(profile)
            await db.sms_campaigns.update_one({"id": campaign_id}, {"$set": {
                "status": "scheduled", "scheduled_for": nxt.isoformat() if nxt else None}})
            return
        creds = await get_twilio_creds(db, cid)
        client = get_twilio_client_from_creds(creds) if creds else None
        for r in camp["recipients"]:
            if r["status"] != "pending":
                continue
            allowed, reason = await can_send_sms(db, cid, r["phone_e164"], "marketing")
            if not allowed or not client:
                upd = {"status": "blocked", "reason": reason or "Twilio not connected"}
            else:
                try:
                    msg = await asyncio.to_thread(client.messages.create,
                                                  messaging_service_sid=creds["messaging_service_sid"],
                                                  to=r["phone_e164"], body=r["body"])
                    upd = {"status": "sent", "sid": msg.sid, "sent_at": _now_iso()}
                    await db.voice_usage.insert_one({"id": str(uuid.uuid4()), "clinic_id": cid, "kind": "sms", "seconds": 0,
                                                     "metadata": {"to": r["phone_e164"], "sid": msg.sid, "type": "marketing",
                                                                  "campaign_id": campaign_id}, "at": _now_iso()})
                except Exception as e:
                    upd = {"status": "failed", "reason": str(e)[:200]}
            await db.sms_campaigns.update_one(
                {"id": campaign_id, "recipients.phone_e164": r["phone_e164"]},
                {"$set": {f"recipients.$.{k}": v for k, v in upd.items()}})
        final = await db.sms_campaigns.find_one({"id": campaign_id}, {"_id": 0, "recipients": 1})
        counts = {k: sum(1 for r in final["recipients"] if r["status"] == k) for k in ("sent", "blocked", "failed")}
        await db.sms_campaigns.update_one({"id": campaign_id}, {"$set": {
            "status": "completed", "completed_at": _now_iso(), "results": counts}})

    async def dispatch_due():
        now = _now_iso()
        stale = (datetime.now(timezone.utc) - STALE_SENDING).isoformat()
        while True:
            camp = await db.sms_campaigns.find_one_and_update(
                {"$or": [{"status": "scheduled", "scheduled_for": {"$lte": now}},
                         {"status": "sending", "dispatch_started_at": {"$lt": stale}}]},
                {"$set": {"status": "sending", "dispatch_started_at": now}}, projection={"_id": 0, "id": 1})
            if not camp:
                return
            await dispatch(camp["id"])

    @router.get("/templates")
    async def list_templates(user=Depends(auth_dep)):
        return await db.sms_marketing_templates.find(
            {"clinic_id": user["clinic_id"], "status": "active"}, {"_id": 0}).sort("created_at", -1).to_list(200)

    @router.post("/templates")
    async def create_template(req: TemplateReq, user=Depends(auth_dep)):
        _require_owner(user, "create marketing templates")
        doc = {"id": str(uuid.uuid4()), "clinic_id": user["clinic_id"], "name": req.name, "body": req.body,
               "locked": True, "status": "active", "created_by": user["email"], "created_at": _now_iso()}
        await db.sms_marketing_templates.insert_one({**doc})
        return doc

    @router.delete("/templates/{tid}")
    async def archive_template(tid: str, user=Depends(auth_dep)):
        _require_owner(user, "archive marketing templates")
        r = await db.sms_marketing_templates.update_one(
            {"id": tid, "clinic_id": user["clinic_id"]}, {"$set": {"status": "archived", "archived_at": _now_iso()}})
        if not r.matched_count:
            raise HTTPException(404, "Template not found")
        return {"ok": True}

    @router.post("/audience/preview")
    async def preview(req: AudienceReq, user=Depends(auth_dep)):
        t = await _template(user["clinic_id"], req.template_id)
        a = await _audience(user["clinic_id"], t, req.species)
        return {"eligible_count": len(a["eligible"]), "excluded": a["excluded"], "sample": a["eligible"][:5]}

    @router.get("/campaigns")
    async def list_campaigns(user=Depends(auth_dep)):
        return await db.sms_campaigns.find({"clinic_id": user["clinic_id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)

    @router.post("/campaigns")
    async def create_campaign(req: CampaignReq, user=Depends(auth_dep)):
        cid = user["clinic_id"]
        t = await _template(cid, req.template_id)
        a = await _audience(cid, t, req.species)
        if not a["eligible"]:
            raise HTTPException(400, "No recipients with active marketing consent match this audience.")
        doc = {"id": str(uuid.uuid4()), "clinic_id": cid, "name": req.name, "template_id": t["id"],
               "template_name": t["name"], "template_body": t["body"], "species": req.species or "all",
               "recipients": a["eligible"], "recipient_count": len(a["eligible"]), "excluded": a["excluded"],
               "status": "pending_approval", "created_by": user["email"], "created_at": _now_iso()}
        await db.sms_campaigns.insert_one({**doc})
        return doc

    async def _pending(cid: str, camp_id: str, statuses: tuple) -> dict:
        camp = await db.sms_campaigns.find_one({"id": camp_id, "clinic_id": cid}, {"_id": 0})
        if not camp:
            raise HTTPException(404, "Campaign not found")
        if camp["status"] not in statuses:
            raise HTTPException(400, f"Campaign is {camp['status'].replace('_', ' ')}.")
        return camp

    @router.post("/campaigns/{camp_id}/approve")
    async def approve(camp_id: str, background: BackgroundTasks, user=Depends(auth_dep)):
        _require_owner(user, "approve marketing sends")
        cid = user["clinic_id"]
        camp = await _pending(cid, camp_id, ("pending_approval",))
        if camp["created_by"] == user["email"]:
            # Two-person rule when the clinic has a second owner; a solo-owner clinic may
            # self-approve (the approval itself is the deliberate second step).
            owner_count = await db.users.count_documents({"clinic_id": cid, "role": "owner"})
            if owner_count > 1:
                raise HTTPException(403, "A different owner must approve this blast (two-person rule).")
        reason = await _readiness_reason(cid)
        if reason:
            raise HTTPException(400, reason)
        profile = await db.sms_compliance_profiles.find_one({"clinic_id": cid}) or {}
        quiet = _in_quiet_hours(profile)
        nxt = next_send_window(profile) if quiet else None
        updates = {"approved_by": user["email"], "approved_at": _now_iso(),
                   "status": "scheduled" if quiet else "sending",
                   "scheduled_for": nxt.isoformat() if nxt else None, "dispatch_started_at": _now_iso()}
        claimed = await db.sms_campaigns.find_one_and_update(
            {"id": camp_id, "status": "pending_approval"}, {"$set": updates}, projection={"_id": 0, "id": 1})
        if not claimed:
            raise HTTPException(400, "Campaign was already actioned.")
        if not quiet:
            background.add_task(dispatch, camp_id)
        return {**camp, **updates, "recipients": camp["recipients"]}

    @router.post("/campaigns/{camp_id}/test")
    async def send_test(camp_id: str, user=Depends(auth_dep)):
        _require_owner(user, "send test messages")
        camp = await _pending(user["clinic_id"], camp_id, ("pending_approval",))
        me = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "mobile_phone": 1, "mobile_verified": 1}) or {}
        if not me.get("mobile_verified") or not me.get("mobile_phone"):
            raise HTTPException(400, "Verify your mobile number in Settings first.")
        if len(camp.get("tests") or []) >= TEST_LIMIT_PER_CAMPAIGN:
            raise HTTPException(429, f"Test limit reached ({TEST_LIMIT_PER_CAMPAIGN} per blast).")
        body = "[TEST] " + camp["recipients"][0]["body"]
        entry = {"by": user["email"], "to": me["mobile_phone"], "at": _now_iso(), "body": body}
        try:
            entry["sid"] = await send_raw_sms(db, user["clinic_id"], me["mobile_phone"], body, "marketing_test",
                                              campaign_id=camp_id)
            entry["status"] = "sent"
        except Exception as e:
            entry.update(status="failed", reason=str(e)[:200])
        await db.sms_campaigns.update_one({"id": camp_id}, {"$push": {"tests": entry}})
        if entry["status"] != "sent":
            raise HTTPException(400, f"Test send failed: {entry['reason']}")
        return entry

    @router.get("/campaigns/{camp_id}/results")
    async def results(camp_id: str, user=Depends(auth_dep)):
        cid = user["clinic_id"]
        camp = await db.sms_campaigns.find_one({"id": camp_id, "clinic_id": cid}, {"_id": 0})
        if not camp:
            raise HTTPException(404, "Campaign not found")
        rows, sent = [], [r for r in camp["recipients"] if r["status"] == "sent"]
        phones = [r["phone_e164"] for r in sent]
        pets, pet_owner = {}, {}
        for p in await db.patients.find({"clinic_id": cid, "owner_id": {"$in": [r["owner_id"] for r in sent]}},
                                        {"_id": 0, "id": 1, "owner_id": 1}).to_list(10000):
            pets.setdefault(p["owner_id"], []).append(p["id"])
            pet_owner[p["id"]] = p["owner_id"]
        replies = {}
        async for sess in db.receptionist_sessions.find({"clinic_id": cid, "from_number": {"$in": phones}},
                                                        {"_id": 0, "from_number": 1, "transcript": 1}):
            for t in sess.get("transcript", []):
                if t.get("role") == "user" and _ts(t.get("at")):
                    replies.setdefault(sess["from_number"], []).append(t)
        optouts = {}
        async for ev in db.consent_events.find({"clinic_id": cid, "phone_e164": {"$in": phones}, "consent_type": "marketing",
                                                "action": "opt_out"}, {"_id": 0, "phone_e164": 1, "at": 1}):
            if _ts(ev.get("at")):
                optouts.setdefault(ev["phone_e164"], []).append(ev["at"])
        bookings = {}
        for coll, fields in (("appointments", ("created_at", "datetime")), ("visits", ("date",))):
            async for d in db[coll].find({"clinic_id": cid, "patient_id": {"$in": list(pet_owner)}},
                                         {"_id": 0, "patient_id": 1, **{f: 1 for f in fields}}):
                for f in fields:
                    if _ts(d.get(f)):
                        bookings.setdefault(pet_owner[d["patient_id"]], []).append(d[f])
        for r in camp["recipients"]:
            row = {k: r.get(k) for k in ("owner_id", "name", "phone_e164", "status", "reason", "sent_at")}
            row.update(replied=None, opted_out_at=None, booked_at=None)
            start = _ts(r.get("sent_at")) if r["status"] == "sent" else None
            if start:
                rep = sorted((t for t in replies.get(r["phone_e164"], []) if start <= _ts(t["at"]) <= start + REPLY_WINDOW),
                             key=lambda t: _ts(t["at"]))
                if rep:
                    row["replied"] = {"at": rep[0]["at"], "text": rep[0].get("text", "")[:160]}
                row["opted_out_at"] = min((a for a in optouts.get(r["phone_e164"], []) if _ts(a) >= start), key=_ts, default=None)
                row["booked_at"] = min((b for b in bookings.get(r["owner_id"], []) if start <= _ts(b) <= start + BOOKING_WINDOW),
                                       key=_ts, default=None)
            rows.append(row)
        n = len(sent)
        rate = lambda k: round(100 * sum(1 for x in rows if x[k]) / n, 1) if n else 0.0
        summary = {"recipients": len(rows), "sent": n,
                   "blocked": sum(1 for x in rows if x["status"] == "blocked"),
                   "failed": sum(1 for x in rows if x["status"] == "failed"),
                   "replied": sum(1 for x in rows if x["replied"]), "opted_out": sum(1 for x in rows if x["opted_out_at"]),
                   "booked": sum(1 for x in rows if x["booked_at"]),
                   "reply_rate": rate("replied"), "opt_out_rate": rate("opted_out_at"), "booking_rate": rate("booked_at")}
        return {"campaign": {k: camp.get(k) for k in ("id", "name", "status", "template_name", "approved_by", "completed_at", "created_at")},
                "summary": summary, "rows": rows}

    @router.post("/campaigns/{camp_id}/reject")
    async def reject(camp_id: str, req: RejectReq, user=Depends(auth_dep)):
        _require_owner(user, "reject marketing sends")
        await _pending(user["clinic_id"], camp_id, ("pending_approval",))
        await db.sms_campaigns.update_one({"id": camp_id}, {"$set": {
            "status": "rejected", "rejected_by": user["email"], "rejected_at": _now_iso(), "reject_reason": req.reason}})
        return {"ok": True}

    @router.post("/campaigns/{camp_id}/cancel")
    async def cancel(camp_id: str, user=Depends(auth_dep)):
        camp = await _pending(user["clinic_id"], camp_id, ("pending_approval", "scheduled"))
        if camp["created_by"] != user["email"] and user.get("role", "owner") != "owner":
            raise HTTPException(403, "Only the composer or an owner can cancel.")
        await db.sms_campaigns.update_one({"id": camp_id, "status": camp["status"]}, {"$set": {
            "status": "cancelled", "cancelled_by": user["email"], "cancelled_at": _now_iso()}})
        return {"ok": True}

    cron = APIRouter(prefix="/api/cron")

    @cron.post("/sms-dispatch")
    async def cron_dispatch(request: Request, background: BackgroundTasks):
        # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
        secret = os.environ["WEBHOOK_CRON_SECRET"]
        auth = request.headers.get("authorization", "")
        if not auth.startswith("Bearer ") or not hmac.compare_digest(auth[7:], secret):
            raise HTTPException(401, "Unauthorized")
        run_id = request.headers.get("x-webhook-id") or str(uuid.uuid4())
        if await db.cron_runs.find_one({"run_id": run_id}):
            return {"ok": True, "duplicate": True}
        await db.cron_runs.insert_one({"run_id": run_id, "job": "sms-dispatch", "at": _now_iso()})
        background.add_task(dispatch_due)
        return {"ok": True}

    return router, cron
