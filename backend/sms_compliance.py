"""A2P 10DLC compliance orchestration.

Vetaura is a pure orchestrator — the CLINIC owns their Twilio account, submits their own
Brand & Campaign registration, and is legally responsible for consent. This module gives
clinics the operational tooling they need to run compliant SMS:

  1. `sms_compliance_profiles` — clinic-entered business/brand/campaign attestation.
     Nothing is auto-generated. Clinics manually paste their approved Brand SID / Campaign
     SID from Twilio Console after their own registration is approved.

  2. `consent_records` — immutable ledger. One row per (clinic_id, phone_e164, consent_type)
     with append-only status transitions (opted_in → opted_out → opted_in_again). Every
     transition captures source, disclosure_version, timestamp, and staff/user id.

  3. Outbound send gate — before we send an SMS on the clinic's behalf, we check:
       (a) clinic has a verified Twilio integration + Messaging Service SID
       (b) clinic has attested Brand + Campaign approved
       (c) recipient has an active consent record matching the message_type
       (d) send is within quiet-hours (optional)
     If any check fails, the send is blocked with a specific reason.

  4. STOP/HELP handling — plugged into the SMS inbound webhook.
       STOP → mark all consents for that phone as opted_out (effective immediately)
       HELP → auto-reply with clinic identity + support contact + opt-out instructions.

  5. Message categories: 'care' (transactional: reminders, care updates, refills, replies)
     and 'marketing' (requires SEPARATE explicit consent). Care consent NEVER implies
     marketing consent.
"""
from __future__ import annotations
import re
import uuid
from datetime import datetime, timezone
from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from motor.motor_asyncio import AsyncIOMotorDatabase


CONSENT_TYPES = ("care", "marketing")
STOP_TOKENS = {"STOP", "STOPALL", "UNSUBSCRIBE", "CANCEL", "END", "QUIT", "REVOKE", "OPTOUT"}
HELP_TOKENS = {"HELP", "INFO"}
STOP_ACK = "You are now unsubscribed and will receive no more messages from this number. Reply START to resubscribe."


# Default checklist mirrors A2P 10DLC MVP requirements. Stored per clinic so items can be
# checked off individually and status persists across sessions.
DEFAULT_CHECKLIST = [
    {"key": "twilio_account", "label": "Clinic has a Twilio account with a payment method"},
    {"key": "phone_number", "label": "Clinic has purchased (or ported) a U.S. 10-digit long code"},
    {"key": "brand_registered", "label": "Clinic Brand registered and approved in Twilio Console"},
    {"key": "campaign_registered", "label": "Clinic Campaign (Customer Care / Account Notifications) approved"},
    {"key": "messaging_service", "label": "Messaging Service created and phone number attached to it"},
    {"key": "website_privacy", "label": "Website has a Privacy Policy and SMS Terms page linked publicly"},
    {"key": "opt_in_evidence", "label": "Opt-in method live on website / intake form (screenshot on file)"},
    {"key": "sample_messages", "label": "Sample messages submitted to Twilio match approved templates"},
    {"key": "stop_help_flow", "label": "STOP / HELP replies configured (Vetaura handles these automatically)"},
    {"key": "consent_ledger", "label": "Existing client consent has been imported to Vetaura, or new-consent workflow is live"},
    {"key": "api_key_connected", "label": "Restricted Twilio API Key created and connected to Vetaura"},
]


class ProfileReq(BaseModel):
    legal_business_name: Optional[str] = None
    dba: Optional[str] = None
    ein: Optional[str] = None
    entity_type: Optional[str] = None
    business_address: Optional[str] = None
    business_website: Optional[str] = None
    business_email: Optional[EmailStr] = None
    business_phone: Optional[str] = None
    authorized_contact_name: Optional[str] = None
    authorized_contact_email: Optional[EmailStr] = None
    texting_purpose: Optional[str] = None  # free text description
    campaign_use_case: Optional[Literal["customer_care", "account_notifications", "delivery_notifications", "marketing", "mixed"]] = None
    sample_messages: Optional[list[str]] = None
    opt_in_url: Optional[str] = None
    disclosure_language: Optional[str] = None  # what THEIR opt-in text says (verbatim)
    brand_sid: Optional[str] = None      # from Twilio Console after approval
    campaign_sid: Optional[str] = None
    brand_status: Optional[Literal["not_started", "pending", "approved", "rejected"]] = None
    campaign_status: Optional[Literal["not_started", "pending", "approved", "rejected"]] = None
    checklist: Optional[dict[str, bool]] = None
    quiet_hours_start: Optional[str] = None  # "21:00"
    quiet_hours_end: Optional[str] = None    # "09:00"
    quiet_hours_tz: Optional[str] = None     # "America/Los_Angeles"


class ConsentReq(BaseModel):
    phone_e164: str = Field(min_length=8, max_length=20)
    consent_type: Literal["care", "marketing"] = "care"
    source: str = Field(min_length=1, max_length=120)   # e.g. "intake_form_v3", "in_person_verbal", "kiosk"
    disclosure_version: str = Field(min_length=1, max_length=60)
    contact_name: Optional[str] = None
    contact_id: Optional[str] = None
    proof_url: Optional[str] = None
    notes: Optional[str] = None


class ConsentActionReq(BaseModel):
    phone_e164: str
    consent_type: Literal["care", "marketing"] = "care"
    reason: Optional[str] = None


def _normalize_phone(p: str) -> str:
    """Loose E.164 normalisation. Not exhaustive — we accept any digits with optional +."""
    digits = re.sub(r"[^\d+]", "", p or "")
    if digits and not digits.startswith("+"):
        # If it's 10 digits, assume US.
        if len(digits) == 10:
            digits = "+1" + digits
        elif len(digits) == 11 and digits.startswith("1"):
            digits = "+" + digits
    return digits


async def record_consent_transition(db: AsyncIOMotorDatabase, clinic_id: str, phone: str,
                                    consent_type: str, action: Literal["opt_in", "opt_out"],
                                    source: str, disclosure_version: str = "",
                                    actor: Optional[str] = None, notes: str = ""):
    """Append-only ledger row + updates the 'current status' materialised row."""
    phone = _normalize_phone(phone)
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "clinic_id": clinic_id,
        "phone_e164": phone,
        "consent_type": consent_type,
        "action": action,
        "source": source,
        "disclosure_version": disclosure_version,
        "actor": actor or "",
        "notes": notes or "",
        "at": now,
    }
    await db.consent_events.insert_one(doc)
    doc.pop("_id", None)
    await db.consent_records.update_one(
        {"clinic_id": clinic_id, "phone_e164": phone, "consent_type": consent_type},
        {"$set": {
            "clinic_id": clinic_id,
            "phone_e164": phone,
            "consent_type": consent_type,
            "status": "opted_in" if action == "opt_in" else "opted_out",
            "last_source": source,
            "last_disclosure_version": disclosure_version,
            "last_actor": actor or "",
            "updated_at": now,
        }, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    return doc


async def has_active_consent(db: AsyncIOMotorDatabase, clinic_id: str, phone: str, consent_type: str) -> bool:
    phone = _normalize_phone(phone)
    doc = await db.consent_records.find_one({
        "clinic_id": clinic_id, "phone_e164": phone, "consent_type": consent_type
    })
    return bool(doc and doc.get("status") == "opted_in")


def _in_quiet_hours(profile: dict, now: Optional[datetime] = None) -> bool:
    """True if `now` falls inside the clinic's quiet-hours window in the clinic's TZ.
    Also treats Sundays as a quiet day for marketing by default."""
    start = (profile.get("quiet_hours_start") or "").strip()
    end = (profile.get("quiet_hours_end") or "").strip()
    tz_name = (profile.get("quiet_hours_tz") or "America/Los_Angeles").strip()
    now = now or datetime.now(timezone.utc)
    try:
        try:
            from zoneinfo import ZoneInfo
            local = now.astimezone(ZoneInfo(tz_name))
        except Exception:
            local = now
    except Exception:
        local = now
    # Sundays are always quiet for marketing (industry hygiene). We express this by returning
    # True on Sunday whenever a quiet-hours window is configured at all.
    if local.weekday() == 6 and (start or end):
        return True
    if not start or not end:
        return False
    def _parse(t: str):
        try:
            hh, mm = t.split(":")
            return int(hh), int(mm)
        except Exception:
            return None
    s = _parse(start); e = _parse(end)
    if not s or not e:
        return False
    cur = local.hour * 60 + local.minute
    smin = s[0] * 60 + s[1]
    emin = e[0] * 60 + e[1]
    if smin == emin:
        return False
    if smin < emin:
        return smin <= cur < emin
    # window crosses midnight
    return cur >= smin or cur < emin


def is_stop_message(body: str) -> bool:
    tokens = re.findall(r"[A-Za-z]+", (body or "").upper())
    if not tokens:
        return False
    return tokens[0] in STOP_TOKENS


def is_help_message(body: str) -> bool:
    tokens = re.findall(r"[A-Za-z]+", (body or "").upper())
    if not tokens:
        return False
    return tokens[0] in HELP_TOKENS


def is_start_message(body: str) -> bool:
    tokens = re.findall(r"[A-Za-z]+", (body or "").upper())
    return bool(tokens and tokens[0] in {"START", "UNSTOP", "YES"})


def build_help_reply(profile: dict, clinic_name: str) -> str:
    contact = profile.get("business_phone") or profile.get("business_email") or ""
    contact_line = f" Contact us at {contact}." if contact else ""
    return f"{clinic_name}: automated messaging support.{contact_line} Msg&data rates may apply. Reply STOP to opt out, HELP for help."


async def can_send_sms(db: AsyncIOMotorDatabase, clinic_id: str, phone: str,
                       message_type: Literal["care", "marketing"] = "care") -> tuple[bool, str]:
    """Returns (allowed, reason). Reason is empty when allowed."""
    profile = await db.sms_compliance_profiles.find_one({"clinic_id": clinic_id}) or {}
    if profile.get("brand_status") != "approved" or profile.get("campaign_status") != "approved":
        return False, "Brand or Campaign not yet approved by the clinic in Twilio Console."
    creds = await db.twilio_credentials.find_one({"clinic_id": clinic_id})
    if not creds or not creds.get("messaging_service_sid"):
        return False, "Twilio Messaging Service is not connected."
    if not await has_active_consent(db, clinic_id, phone, message_type):
        return False, f"Recipient has no active {message_type} consent."
    # Marketing must respect quiet hours; care is not blocked by quiet hours (transactional).
    if message_type == "marketing" and _in_quiet_hours(profile):
        return False, "Marketing sends are paused during clinic quiet hours."
    return True, ""


def build_compliance_routes(db: AsyncIOMotorDatabase, auth_dep):
    router = APIRouter(prefix="/api/compliance/sms")

    async def _seed_profile(clinic_id: str) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "clinic_id": clinic_id,
            "checklist": {item["key"]: False for item in DEFAULT_CHECKLIST},
            "checklist_definitions": DEFAULT_CHECKLIST,
            "brand_status": "not_started",
            "campaign_status": "not_started",
            "sample_messages": [],
            "created_at": now,
            "updated_at": now,
        }
        await db.sms_compliance_profiles.insert_one({**doc})
        doc.pop("_id", None)
        return doc

    def _readiness(profile: dict, twilio_creds: dict | None) -> dict:
        checks = profile.get("checklist") or {}
        completed = sum(1 for v in checks.values() if v)
        total = len(DEFAULT_CHECKLIST)
        connected = bool(twilio_creds)
        brand_ok = profile.get("brand_status") == "approved"
        camp_ok = profile.get("campaign_status") == "approved"
        msg_svc_ok = bool(twilio_creds and twilio_creds.get("messaging_service_sid"))
        ready = connected and brand_ok and camp_ok and msg_svc_ok and completed == total
        state = "ready" if ready else (
            "blocked" if not connected else
            "brand_pending" if not brand_ok else
            "campaign_pending" if not camp_ok else
            "messaging_service_missing" if not msg_svc_ok else
            "action_needed"
        )
        return {"ready": ready, "state": state, "checklist_completed": completed, "checklist_total": total}

    @router.get("/profile")
    async def get_profile(user=Depends(auth_dep)):
        cid = user["clinic_id"]
        doc = await db.sms_compliance_profiles.find_one({"clinic_id": cid}, {"_id": 0})
        if not doc:
            doc = await _seed_profile(cid)
        # merge in any missing checklist keys (schema evolution safe)
        checks = doc.get("checklist") or {}
        for item in DEFAULT_CHECKLIST:
            checks.setdefault(item["key"], False)
        doc["checklist"] = checks
        doc["checklist_definitions"] = DEFAULT_CHECKLIST
        twilio_creds = await db.twilio_credentials.find_one({"clinic_id": cid}, {"_id": 0, "api_key_secret_encrypted": 0})
        doc["readiness"] = _readiness(doc, twilio_creds)
        return doc

    @router.patch("/profile")
    async def patch_profile(req: ProfileReq, user=Depends(auth_dep)):
        cid = user["clinic_id"]
        # ensure exists
        existing = await db.sms_compliance_profiles.find_one({"clinic_id": cid})
        if not existing:
            await _seed_profile(cid)
        updates = {k: v for k, v in req.model_dump().items() if v is not None}
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.sms_compliance_profiles.update_one({"clinic_id": cid}, {"$set": updates})
        return await get_profile(user)  # type: ignore

    @router.post("/consent")
    async def opt_in(req: ConsentReq, user=Depends(auth_dep)):
        doc = await record_consent_transition(
            db, user["clinic_id"], req.phone_e164, req.consent_type,
            "opt_in", req.source, req.disclosure_version,
            actor=user["email"], notes=req.notes or "",
        )
        return doc

    @router.post("/consent/opt-out")
    async def opt_out(req: ConsentActionReq, user=Depends(auth_dep)):
        doc = await record_consent_transition(
            db, user["clinic_id"], req.phone_e164, req.consent_type,
            "opt_out", source="staff_manual", actor=user["email"], notes=req.reason or "",
        )
        return doc

    @router.get("/consent")
    async def list_consent(user=Depends(auth_dep), status: Optional[str] = None, consent_type: Optional[str] = None):
        q = {"clinic_id": user["clinic_id"]}
        if status:
            q["status"] = status
        if consent_type:
            q["consent_type"] = consent_type
        rows = await db.consent_records.find(q, {"_id": 0}).sort("updated_at", -1).to_list(500)
        return rows

    @router.get("/consent/events")
    async def list_consent_events(user=Depends(auth_dep), phone: Optional[str] = None):
        q = {"clinic_id": user["clinic_id"]}
        if phone:
            q["phone_e164"] = _normalize_phone(phone)
        rows = await db.consent_events.find(q, {"_id": 0}).sort("at", -1).to_list(500)
        return rows

    @router.get("/preflight")
    async def preflight(user=Depends(auth_dep), phone: str = "", message_type: str = "care"):
        if not phone:
            raise HTTPException(400, "phone is required")
        if message_type not in CONSENT_TYPES:
            raise HTTPException(400, "message_type must be 'care' or 'marketing'")
        allowed, reason = await can_send_sms(db, user["clinic_id"], phone, message_type)
        return {"allowed": allowed, "reason": reason, "phone": _normalize_phone(phone), "message_type": message_type}

    return router
