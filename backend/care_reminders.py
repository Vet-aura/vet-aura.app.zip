"""Vaccine / preventive-care due dates -> automatic care SMS reminders from the clinic's number."""
from __future__ import annotations
import hmac
import logging
import os
import re
import uuid
from datetime import datetime, timezone, timedelta, date
from typing import Literal, Optional
from zoneinfo import ZoneInfo
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from pymongo.errors import DuplicateKeyError
from motor.motor_asyncio import AsyncIOMotorDatabase
from sms_compliance import _normalize_phone, quiet_settings, can_send_sms
from sms_sender import send_raw_sms

logger = logging.getLogger(__name__)
MERGE_FIELDS = {"first_name", "pet_name", "item", "due_date", "due_phrase", "clinic_name"}
DEFAULT_TEMPLATE = "Hi {first_name}, a reminder that {pet_name}'s {item} {due_phrase}. Reply or call us to book."
DEFAULT_SETTINGS = {"enabled": True, "offsets": [14, 0, -7], "send_hour": 10, "template": DEFAULT_TEMPLATE}
STALE_AFTER_DAYS = 21
MAX_ATTEMPTS_PER_STAGE = 3
STALE_PROCESSING = timedelta(minutes=30)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CareItemReq(BaseModel):
    patient_id: str
    kind: Literal["vaccine", "preventive"] = "vaccine"
    name: str = Field(min_length=1, max_length=80)
    due_date: date


class CareItemPatch(BaseModel):
    kind: Optional[Literal["vaccine", "preventive"]] = None
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    due_date: Optional[date] = None


class SettingsReq(BaseModel):
    enabled: bool
    offsets: list[int] = Field(min_length=1, max_length=6)
    send_hour: int = Field(ge=6, le=20)
    template: str = Field(min_length=10, max_length=400)

    @field_validator("offsets")
    @classmethod
    def _offs(cls, v):
        if any(o < -60 or o > 90 for o in v):
            raise ValueError("Offsets must be between 60 days overdue and 90 days before")
        return sorted(set(v), reverse=True)

    @field_validator("template")
    @classmethod
    def _tpl(cls, v):
        bad = set(re.findall(r"\{(\w+)\}", v)) - MERGE_FIELDS
        if bad:
            raise ValueError(f"Unsupported merge field(s): {', '.join(sorted(bad))}")
        return v.strip()


def current_stage(days_until: int, offsets: list[int]) -> Optional[int]:
    """Latest reminder stage reached (e.g. offsets [14,0,-7]; 10 days out -> 14, due today -> 0)."""
    reached = [o for o in offsets if days_until <= o]
    if not reached or days_until < min(offsets) - STALE_AFTER_DAYS:
        return None
    return min(reached)


def due_phrase(days_until: int) -> str:
    if days_until > 1:
        return f"is due in {days_until} days"
    if days_until == 1:
        return "is due tomorrow"
    if days_until == 0:
        return "is due today"
    return f"is {abs(days_until)} day{'s' if days_until != -1 else ''} overdue"


def build_reminder_routes(db: AsyncIOMotorDatabase, auth_dep):
    router = APIRouter(prefix="/api/reminders")

    async def get_settings(cid: str) -> dict:
        doc = await db.reminder_settings.find_one({"clinic_id": cid}, {"_id": 0}) or {}
        return {**DEFAULT_SETTINGS, **{k: v for k, v in doc.items() if k in DEFAULT_SETTINGS}, "last_run_date": doc.get("last_run_date")}

    async def _clinic_today(cid: str) -> date:
        profile = await db.sms_compliance_profiles.find_one({"clinic_id": cid}) or {}
        return datetime.now(ZoneInfo(quiet_settings(profile)["quiet_hours_tz"])).date()

    async def _candidates(cid: str, settings: dict, today: date, horizon: int = 0) -> list[dict]:
        """Items whose current stage (as of today + horizon) has not been sent yet."""
        items = await db.care_items.find({"clinic_id": cid, "status": "due"}, {"_id": 0}).to_list(5000)
        if not items:
            return []
        patients = {p["id"]: p for p in await db.patients.find(
            {"clinic_id": cid, "id": {"$in": list({i["patient_id"] for i in items})}}, {"_id": 0}).to_list(5000)}
        owners = {o["id"]: o for o in await db.owners.find({"clinic_id": cid}, {"_id": 0}).to_list(5000)}
        sent, attempts = set(), {}
        for s in await db.reminder_sends.find({"clinic_id": cid, "item_id": {"$in": [i["id"] for i in items]}},
                                              {"_id": 0, "item_id": 1, "stage": 1, "dedupe_key": 1}).to_list(20000):
            k = (s["item_id"], s["stage"])
            attempts[k] = attempts.get(k, 0) + 1
            if s.get("dedupe_key") or attempts[k] >= MAX_ATTEMPTS_PER_STAGE:
                sent.add(k)
        out = []
        for it in items:
            p = patients.get(it["patient_id"])
            o = owners.get((p or {}).get("owner_id"))
            if not p or not o:
                continue
            due = date.fromisoformat(it["due_date"])
            for ahead in range(horizon + 1):
                d = today + timedelta(days=ahead)
                stage = current_stage((due - d).days, settings["offsets"])
                if stage is not None and (it["id"], stage) not in sent:
                    out.append({"item": it, "patient": p, "owner": o, "stage": stage, "send_on": d.isoformat(),
                                "days_until": (due - d).days, "phone_e164": _normalize_phone(o.get("phone", ""))})
                    break
        return sorted(out, key=lambda c: c["send_on"])

    async def run_clinic(cid: str, trigger: str) -> dict:
        settings = await get_settings(cid)
        today = await _clinic_today(cid)
        clinic = await db.clinics.find_one({"clinic_id": cid}, {"_id": 0, "name": 1}) or {}
        counts = {"sent": 0, "blocked": 0, "failed": 0}
        stale = (datetime.now(timezone.utc) - STALE_PROCESSING).isoformat()
        await db.reminder_sends.update_many({"clinic_id": cid, "status": "processing", "at": {"$lt": stale}},
                                            {"$set": {"status": "failed", "reason": "Interrupted before sending"},
                                             "$unset": {"dedupe_key": ""}})
        for c in await _candidates(cid, settings, today):
            ctx = {"first_name": (c["owner"].get("name") or "").split(" ")[0], "pet_name": c["patient"]["name"],
                   "item": c["item"]["name"], "due_date": date.fromisoformat(c["item"]["due_date"]).strftime("%b %-d"),
                   "due_phrase": due_phrase(c["days_until"]), "clinic_name": clinic.get("name", "")}
            body = re.sub(r"\{(\w+)\}", lambda m: str(ctx.get(m.group(1), "")), settings["template"]).rstrip()
            body += f" — {clinic.get('name', '')}. Reply STOP to opt out."
            rec = {"id": str(uuid.uuid4()), "clinic_id": cid, "item_id": c["item"]["id"], "stage": c["stage"],
                   "patient_id": c["patient"]["id"], "patient_name": c["patient"]["name"], "owner_name": c["owner"].get("name"),
                   "item_name": c["item"]["name"], "due_date": c["item"]["due_date"], "phone_e164": c["phone_e164"],
                   "body": body, "trigger": trigger, "status": "processing", "at": _now_iso(),
                   "dedupe_key": f"{c['item']['id']}:{c['stage']}"}
            try:
                await db.reminder_sends.insert_one({**rec})
            except DuplicateKeyError:
                continue
            allowed, reason = await can_send_sms(db, cid, c["phone_e164"], "care")
            if not allowed:
                upd = {"status": "blocked", "reason": reason}
            else:
                try:
                    sid = await send_raw_sms(db, cid, c["phone_e164"], body, "care_reminder", item_id=c["item"]["id"])
                    upd = {"status": "sent", "sid": sid}
                except Exception as e:
                    upd = {"status": "failed", "reason": str(e)[:200]}
            counts[upd["status"]] += 1
            op = {"$set": upd}
            if upd["status"] != "sent":
                op["$unset"] = {"dedupe_key": ""}
            await db.reminder_sends.update_one({"id": rec["id"]}, op)
        marker = {"last_run_at": _now_iso()}
        if trigger == "schedule":
            marker["last_run_date"] = today.isoformat()
        await db.reminder_settings.update_one({"clinic_id": cid}, {"$set": marker}, upsert=True)
        return counts

    async def run_due_clinics():
        for cid in await db.care_items.distinct("clinic_id", {"status": "due"}):
            try:
                settings = await get_settings(cid)
                if not settings["enabled"]:
                    continue
                profile = await db.sms_compliance_profiles.find_one({"clinic_id": cid}) or {}
                q = quiet_settings(profile)
                local = datetime.now(ZoneInfo(q["quiet_hours_tz"]))
                if local.hour < settings["send_hour"] or local.weekday() in q["quiet_days"]:
                    continue
                if settings.get("last_run_date") == local.date().isoformat():
                    continue
                await run_clinic(cid, "schedule")
            except Exception as e:
                logger.warning(f"Care reminder run failed for {cid}: {e}")

    def _owner(user):
        if user.get("role", "owner") != "owner":
            raise HTTPException(403, "Only clinic owners can change reminder automation.")

    async def _patient(cid: str, pid: str):
        if not await db.patients.find_one({"clinic_id": cid, "id": pid}, {"_id": 1}):
            raise HTTPException(404, "Patient not found")

    @router.get("/items")
    async def list_items(patient_id: Optional[str] = None, user=Depends(auth_dep)):
        q = {"clinic_id": user["clinic_id"]}
        if patient_id:
            q["patient_id"] = patient_id
        return await db.care_items.find(q, {"_id": 0}).sort("due_date", 1).to_list(2000)

    @router.post("/items")
    async def create_item(req: CareItemReq, user=Depends(auth_dep)):
        await _patient(user["clinic_id"], req.patient_id)
        doc = {"id": str(uuid.uuid4()), "clinic_id": user["clinic_id"], "patient_id": req.patient_id, "kind": req.kind,
               "name": req.name.strip(), "due_date": req.due_date.isoformat(), "status": "due",
               "created_by": user["email"], "created_at": _now_iso()}
        await db.care_items.insert_one({**doc})
        return doc

    @router.patch("/items/{item_id}")
    async def update_item(item_id: str, req: CareItemPatch, user=Depends(auth_dep)):
        upd = {k: (v.isoformat() if isinstance(v, date) else v) for k, v in req.model_dump().items() if v is not None}
        if not upd:
            raise HTTPException(400, "Nothing to update")
        doc = await db.care_items.find_one_and_update({"id": item_id, "clinic_id": user["clinic_id"]}, {"$set": upd},
                                                      projection={"_id": 0}, return_document=True)
        if not doc:
            raise HTTPException(404, "Care item not found")
        return doc

    @router.post("/items/{item_id}/complete")
    async def complete_item(item_id: str, user=Depends(auth_dep)):
        r = await db.care_items.update_one({"id": item_id, "clinic_id": user["clinic_id"]}, {"$set": {
            "status": "done", "completed_at": _now_iso(), "completed_by": user["email"]}})
        if not r.matched_count:
            raise HTTPException(404, "Care item not found")
        return {"ok": True}

    @router.delete("/items/{item_id}")
    async def delete_item(item_id: str, user=Depends(auth_dep)):
        r = await db.care_items.delete_one({"id": item_id, "clinic_id": user["clinic_id"]})
        if not r.deleted_count:
            raise HTTPException(404, "Care item not found")
        return {"ok": True}

    @router.get("/settings")
    async def read_settings(user=Depends(auth_dep)):
        return await get_settings(user["clinic_id"])

    @router.put("/settings")
    async def write_settings(req: SettingsReq, user=Depends(auth_dep)):
        _owner(user)
        await db.reminder_settings.update_one({"clinic_id": user["clinic_id"]}, {"$set": {
            **req.model_dump(), "clinic_id": user["clinic_id"], "updated_by": user["email"], "updated_at": _now_iso()}}, upsert=True)
        return await get_settings(user["clinic_id"])

    @router.get("/upcoming")
    async def upcoming(days: int = 30, user=Depends(auth_dep)):
        cid = user["clinic_id"]
        settings = await get_settings(cid)
        rows = await _candidates(cid, settings, await _clinic_today(cid), horizon=max(0, min(days, 90)))
        consent = {r["phone_e164"]: r["status"] for r in await db.consent_records.find(
            {"clinic_id": cid, "consent_type": "care"}, {"_id": 0}).to_list(10000)}
        return [{"item_id": r["item"]["id"], "item_name": r["item"]["name"], "kind": r["item"]["kind"],
                 "due_date": r["item"]["due_date"], "patient_id": r["patient"]["id"], "patient_name": r["patient"]["name"],
                 "owner_name": r["owner"].get("name"), "phone_e164": r["phone_e164"], "stage": r["stage"],
                 "send_on": r["send_on"], "care_consent": consent.get(r["phone_e164"], "none")} for r in rows]

    @router.get("/log")
    async def send_log(user=Depends(auth_dep)):
        return await db.reminder_sends.find({"clinic_id": user["clinic_id"]}, {"_id": 0, "dedupe_key": 0}).sort("at", -1).to_list(300)

    @router.post("/run")
    async def run_now(user=Depends(auth_dep)):
        _owner(user)
        return await run_clinic(user["clinic_id"], "manual")

    cron = APIRouter(prefix="/api/cron")

    @cron.post("/care-reminders")
    async def cron_reminders(request: Request, background: BackgroundTasks):
        # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
        auth = request.headers.get("authorization", "")
        if not auth.startswith("Bearer ") or not hmac.compare_digest(auth[7:], os.environ["WEBHOOK_CRON_SECRET"]):
            raise HTTPException(401, "Unauthorized")
        run_id = request.headers.get("x-webhook-id") or str(uuid.uuid4())
        if await db.cron_runs.find_one({"run_id": run_id}):
            return {"ok": True, "duplicate": True}
        await db.cron_runs.insert_one({"run_id": run_id, "job": "care-reminders", "at": _now_iso()})
        background.add_task(run_due_clinics)
        return {"ok": True}

    async def ensure_indexes_and_backfill():
        info = await db.reminder_sends.index_information()
        if "item_id_1_stage_1" in info:
            await db.reminder_sends.drop_index("item_id_1_stage_1")
        await db.reminder_sends.update_many({"status": "sent", "dedupe_key": {"$exists": False}},
                                            [{"$set": {"dedupe_key": {"$concat": ["$item_id", ":", {"$toString": "$stage"}]}}}])
        await db.reminder_sends.create_index("dedupe_key", unique=True, sparse=True)
        await db.reminder_sends.create_index([("clinic_id", 1), ("item_id", 1)])
        await db.care_items.create_index([("clinic_id", 1), ("patient_id", 1)])
        from seed_data import build_care_items
        seeded = set(await db.care_items.distinct("clinic_id"))
        for cid in await db.patients.distinct("clinic_id"):
            if cid in seeded:
                continue
            pats = await db.patients.find({"clinic_id": cid}, {"_id": 0}).sort("_id", 1).to_list(4)
            if len(pats) >= 4:
                await db.care_items.insert_many(build_care_items(cid, pats))

    return router, cron, ensure_indexes_and_backfill
