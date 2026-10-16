"""Marketing bulk SMS: locked templates, marketing-consent audience, two-person approval, quiet-hours queue."""
from __future__ import annotations
import asyncio
import hmac
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from motor.motor_asyncio import AsyncIOMotorDatabase
from sms_compliance import _normalize_phone, _in_quiet_hours, next_send_window, can_send_sms
from credentials_service import get_twilio_creds, get_twilio_client_from_creds

logger = logging.getLogger(__name__)
MERGE_FIELDS = {"first_name", "pet_name", "clinic_name"}
OPT_OUT_SUFFIX = " Reply STOP to opt out."


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
                                 "body": render(template["body"], ctx), "status": "pending"})
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
        clinic = await db.clinics.find_one({"clinic_id": cid}, {"_id": 0, "name": 1}) or {}
        client = get_twilio_client_from_creds(creds) if creds else None
        counts = {"sent": 0, "blocked": 0, "failed": 0}
        recipients = camp["recipients"]
        for r in recipients:
            if r["status"] != "pending":
                continue
            allowed, reason = await can_send_sms(db, cid, r["phone_e164"], "marketing")
            if not allowed or not client:
                r.update(status="blocked", reason=reason or "Twilio not connected")
                counts["blocked"] += 1
                continue
            try:
                msg = await asyncio.to_thread(client.messages.create,
                                              messaging_service_sid=creds["messaging_service_sid"],
                                              to=r["phone_e164"], body=f"{r['body']} — {clinic.get('name', '')}.{OPT_OUT_SUFFIX}")
                r.update(status="sent", sid=msg.sid, sent_at=_now_iso())
                counts["sent"] += 1
                await db.voice_usage.insert_one({"id": str(uuid.uuid4()), "clinic_id": cid, "kind": "sms", "seconds": 0,
                                                 "metadata": {"to": r["phone_e164"], "sid": msg.sid, "type": "marketing",
                                                              "campaign_id": campaign_id}, "at": _now_iso()})
            except Exception as e:
                r.update(status="failed", reason=str(e)[:200])
                counts["failed"] += 1
        await db.sms_campaigns.update_one({"id": campaign_id}, {"$set": {
            "recipients": recipients, "status": "completed", "completed_at": _now_iso(), "results": counts}})

    async def dispatch_due():
        now = _now_iso()
        while True:
            camp = await db.sms_campaigns.find_one_and_update(
                {"status": "scheduled", "scheduled_for": {"$lte": now}},
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
            raise HTTPException(403, "A different owner must approve this blast (two-person rule).")
        reason = await _readiness_reason(cid)
        if reason:
            raise HTTPException(400, reason)
        profile = await db.sms_compliance_profiles.find_one({"clinic_id": cid}) or {}
        quiet = _in_quiet_hours(profile)
        nxt = next_send_window(profile) if quiet else None
        updates = {"approved_by": user["email"], "approved_at": _now_iso(),
                   "status": "scheduled" if quiet else "sending",
                   "scheduled_for": nxt.isoformat() if nxt else None}
        await db.sms_campaigns.update_one({"id": camp_id, "status": "pending_approval"}, {"$set": updates})
        if not quiet:
            background.add_task(dispatch, camp_id)
        return {**camp, **updates, "recipients": camp["recipients"]}

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
