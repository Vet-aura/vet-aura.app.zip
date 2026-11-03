"""Guided Twilio setup: progress tracking + live, read-only connection checks (nothing is sent)."""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorDatabase
from credentials_service import TwilioCredsReq, get_twilio_creds

STEPS = ["account", "number", "messaging_service", "a2p", "api_key", "connect", "webhooks"]
CHECK_LIMIT_PER_10_MIN = 20


class ProgressReq(BaseModel):
    completed: list[str] = Field(max_length=len(STEPS))


def _check(key: str, label: str, status: str, detail: str = "") -> dict:
    return {"key": key, "label": label, "status": status, "detail": detail}


def _err(e: Exception) -> str:
    code = getattr(e, "code", None)
    msg = getattr(e, "msg", None) or str(e)
    return f"{msg[:160]}" + (f" (Twilio error {code})" if code else "")


def run_checks(account_sid: str, api_key_sid: str, api_key_secret: str, messaging_service_sid: Optional[str]) -> list[dict]:
    """Read-only Twilio calls. Each step degrades to 'warn'/'fail' with a plain-English reason."""
    from twilio.rest import Client
    client = Client(api_key_sid, api_key_secret, account_sid)
    out = []
    try:
        acct = client.api.accounts(account_sid).fetch()
    except Exception as e:
        return [_check("credentials", "API key works", "fail",
                       f"Twilio rejected the Account SID / API Key pair: {_err(e)}. Re-copy the SID and secret.")]
    out.append(_check("credentials", "API key works", "pass", f"Connected to “{acct.friendly_name}”."))
    if str(acct.type).lower() == "trial":
        out.append(_check("account_type", "Upgraded account", "warn",
                          "This is a Trial account — it can only text verified numbers and adds a trial prefix. Upgrade in Twilio Console → Billing."))
    else:
        out.append(_check("account_type", "Upgraded account", "pass", "Paid account."))
    if not messaging_service_sid:
        out.append(_check("messaging_service", "Messaging Service", "fail",
                          "No Messaging Service SID (MG…) entered. All texts must go through a Messaging Service tied to your A2P campaign."))
        return out
    try:
        svc = client.messaging.v1.services(messaging_service_sid).fetch()
        out.append(_check("messaging_service", "Messaging Service", "pass", f"Found “{svc.friendly_name}”."))
    except Exception as e:
        out.append(_check("messaging_service", "Messaging Service", "fail",
                          f"Couldn't open this Messaging Service with your key: {_err(e)}. Check the MG… SID and that the key can read Messaging Services."))
        return out
    try:
        nums = client.messaging.v1.services(messaging_service_sid).phone_numbers.list(limit=20)
        if nums:
            out.append(_check("senders", "Phone number in sender pool", "pass",
                              ", ".join(n.phone_number for n in nums[:3]) + (" …" if len(nums) > 3 else "")))
        else:
            out.append(_check("senders", "Phone number in sender pool", "fail",
                              "The Messaging Service has no phone numbers. Open it → Sender Pool → Add Senders → pick your number."))
    except Exception as e:
        out.append(_check("senders", "Phone number in sender pool", "warn", f"Couldn't list senders (key permission?): {_err(e)}"))
    try:
        camps = client.messaging.v1.services(messaging_service_sid).us_app_to_person.list(limit=5)
        if not camps:
            out.append(_check("a2p", "A2P 10DLC campaign", "fail",
                              "No A2P campaign is linked to this Messaging Service. US carriers block unregistered business texting."))
        else:
            st = (camps[0].campaign_status or "").upper()
            if st == "VERIFIED":
                out.append(_check("a2p", "A2P 10DLC campaign", "pass", "Campaign verified by carriers."))
            elif st == "FAILED":
                out.append(_check("a2p", "A2P 10DLC campaign", "fail", "Campaign was rejected. Review the reason in Twilio Console and resubmit."))
            else:
                out.append(_check("a2p", "A2P 10DLC campaign", "warn", f"Campaign status: {st or 'pending'}. Reviews usually take a few days."))
    except Exception as e:
        out.append(_check("a2p", "A2P 10DLC campaign", "warn", f"Couldn't read campaign status (key permission?): {_err(e)}"))
    return out


def build_twilio_setup_routes(db: AsyncIOMotorDatabase, auth_dep, webhook_base: str):
    router = APIRouter(prefix="/api/integrations/twilio")

    def _owner(user):
        if user.get("role", "owner") != "owner":
            raise HTTPException(403, "Only clinic owners can set up Twilio.")

    async def _throttle(cid: str):
        since = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        if await db.twilio_setup_checks.count_documents({"clinic_id": cid, "at": {"$gte": since}}) >= CHECK_LIMIT_PER_10_MIN:
            raise HTTPException(429, "Too many connection checks. Wait a few minutes and try again.")
        await db.twilio_setup_checks.insert_one({"clinic_id": cid, "at": datetime.now(timezone.utc).isoformat()})

    async def _record(cid: str, checks: list[dict]):
        await db.twilio_setup.update_one({"clinic_id": cid}, {"$set": {
            "clinic_id": cid, "last_checks": checks, "last_checked_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)

    @router.get("/setup")
    async def get_setup(user=Depends(auth_dep)):
        cid = user["clinic_id"]
        doc = await db.twilio_setup.find_one({"clinic_id": cid}, {"_id": 0}) or {}
        creds = await db.twilio_credentials.find_one({"clinic_id": cid}, {"_id": 0, "webhook_token": 1})
        webhooks = None
        if creds and creds.get("webhook_token") and webhook_base:
            base, tok = webhook_base.rstrip("/"), creds["webhook_token"]
            webhooks = {"sms_url": f"{base}/api/twilio/sms/inbound/{cid}/{tok}",
                        "voice_url": f"{base}/api/twilio/voice/inbound/{cid}/{tok}",
                        "voice_status_callback": f"{base}/api/twilio/voice/status/{cid}/{tok}"}
        return {"steps": STEPS, "completed": doc.get("completed", []), "connected": bool(creds),
                "last_checks": doc.get("last_checks"), "last_checked_at": doc.get("last_checked_at"), "webhooks": webhooks}

    @router.put("/setup")
    async def put_setup(req: ProgressReq, user=Depends(auth_dep)):
        _owner(user)
        completed = [s for s in STEPS if s in set(req.completed)]
        await db.twilio_setup.update_one({"clinic_id": user["clinic_id"]}, {"$set": {
            "clinic_id": user["clinic_id"], "completed": completed}}, upsert=True)
        return {"completed": completed}

    @router.post("/check")
    async def check(req: TwilioCredsReq, user=Depends(auth_dep)):
        _owner(user)
        await _throttle(user["clinic_id"])
        checks = await asyncio.to_thread(run_checks, req.account_sid, req.api_key_sid, req.api_key_secret, req.messaging_service_sid)
        return {"checks": checks, "ok": all(c["status"] != "fail" for c in checks)}

    @router.post("/health")
    async def health(user=Depends(auth_dep)):
        _owner(user)
        cid = user["clinic_id"]
        creds = await get_twilio_creds(db, cid)
        if not creds:
            raise HTTPException(400, "Twilio isn't connected (or saved credentials can't be read). Reconnect in the setup guide.")
        await _throttle(cid)
        checks = await asyncio.to_thread(run_checks, creds["account_sid"], creds["api_key_sid"], creds["api_key_secret"],
                                         creds.get("messaging_service_sid"))
        await _record(cid, checks)
        return {"checks": checks, "ok": all(c["status"] != "fail" for c in checks)}

    return router
