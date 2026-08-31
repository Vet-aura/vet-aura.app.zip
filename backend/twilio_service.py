"""Twilio Voice + SMS webhooks for the AI Vet Receptionist.

- Inbound Voice: TwiML greeting → <Gather input="speech"> → Claude reply → repeat.
  Fallback: <Record> the caller's message for offline transcription + staff callback.
- Inbound SMS: MessagingResponse with the AI reply.
- Per-clinic phone number provisioning via Twilio IncomingPhoneNumbers.
- Voice usage metering: each completed call increments `voice_usage` seconds for the clinic.
- Requires TWILIO_ACCOUNT_SID + TWILIO_AUTH_TOKEN. Phone numbers are mapped to clinics via
  a `twilio_numbers` collection so the same webhook URL serves all tenants.
"""
from __future__ import annotations
import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Request, HTTPException, Depends, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_VOICE_WEBHOOK_BASE = os.environ.get("PUBLIC_APP_URL", "")  # e.g. https://vetaura.com


def twilio_configured() -> bool:
    return bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN)


if not TWILIO_AUTH_TOKEN:
    logger.warning("Twilio auth token is unset — signature validation is bypassed. Do NOT ship this to production.")


def _get_twilio_client():
    if not twilio_configured():
        raise HTTPException(503, "Twilio is not configured on this instance.")
    from twilio.rest import Client
    return Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def _validate_signature(request: Request, body_params: dict) -> bool:
    """Verify X-Twilio-Signature. Falls open in dev when TWILIO_AUTH_TOKEN is unset."""
    if not TWILIO_AUTH_TOKEN:
        return True  # dev / demo bypass
    try:
        from twilio.request_validator import RequestValidator
        validator = RequestValidator(TWILIO_AUTH_TOKEN)
        sig = request.headers.get("X-Twilio-Signature", "")
        url = str(request.url)
        return validator.validate(url, body_params, sig)
    except Exception:
        return False


class ProvisionReq(BaseModel):
    area_code: Optional[str] = None
    friendly_name: Optional[str] = None


class ReleaseReq(BaseModel):
    phone_sid: str


class VoicemailStatusReq(BaseModel):
    session_id: str


def _twiml(body: str) -> Response:
    xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<Response>{body}</Response>'
    return Response(content=xml, media_type="application/xml")


def build_twilio_routes(db: AsyncIOMotorDatabase, auth_dep, receptionist_reply_fn, get_or_create_config_fn, emergency_kw_fn, create_task_fn, transcribe_audio_fn):
    router = APIRouter(prefix="/api/twilio")

    async def _clinic_from_number(to_number: str) -> Optional[dict]:
        return await db.twilio_numbers.find_one({"phone_number": to_number}, {"_id": 0})

    async def _log_usage(clinic_id: str, kind: str, seconds: int = 0, cost_cents: int = 0, metadata: dict | None = None):
        await db.voice_usage.insert_one({
            "id": str(uuid.uuid4()),
            "clinic_id": clinic_id,
            "kind": kind,  # 'voice' | 'sms'
            "seconds": int(seconds or 0),
            "cost_cents": int(cost_cents or 0),
            "metadata": metadata or {},
            "at": datetime.now(timezone.utc).isoformat(),
        })

    # ---------- Public webhooks ----------
    @router.post("/voice/inbound")
    async def voice_inbound(request: Request):
        form = dict(await request.form())
        if not _validate_signature(request, form):
            raise HTTPException(403, "Invalid Twilio signature")
        to_number = form.get("To", "")
        from_number = form.get("From", "")
        call_sid = form.get("CallSid", "")

        binding = await _clinic_from_number(to_number)
        if not binding:
            return _twiml('<Say voice="alice">This number is not configured. Goodbye.</Say><Hangup/>')

        cfg = await get_or_create_config_fn(binding["clinic_id"])
        greeting = cfg.get("greeting") or f"Thank you for calling {cfg.get('clinic_name','our clinic')}."
        # Start a session keyed on the CallSid so gather steps chain.
        session_id = f"twilio_{call_sid}"
        await db.receptionist_sessions.update_one(
            {"session_id": session_id, "clinic_id": binding["clinic_id"]},
            {"$setOnInsert": {
                "session_id": session_id, "clinic_id": binding["clinic_id"],
                "transcript": [], "created_at": datetime.now(timezone.utc).isoformat(),
                "channel": "voice", "from_number": from_number, "call_sid": call_sid,
                "status": "active", "handed_off": False,
            }},
            upsert=True,
        )
        gather_action = "/api/twilio/voice/gather"
        body = (
            f'<Say voice="alice">{greeting}</Say>'
            f'<Gather input="speech" action="{gather_action}" method="POST" speechTimeout="auto" timeout="6" language="en-US">'
            f'<Say voice="alice">How can I help you today?</Say>'
            f'</Gather>'
            f'<Say voice="alice">I did not catch that. Please call again or leave a message after the beep.</Say>'
            f'<Record maxLength="90" action="/api/twilio/voice/voicemail" method="POST"/>'
        )
        return _twiml(body)

    @router.post("/voice/gather")
    async def voice_gather(request: Request):
        form = dict(await request.form())
        if not _validate_signature(request, form):
            raise HTTPException(403, "Invalid Twilio signature")
        to_number = form.get("To", "")
        call_sid = form.get("CallSid", "")
        speech = (form.get("SpeechResult") or "").strip()
        binding = await _clinic_from_number(to_number)
        if not binding:
            return _twiml('<Hangup/>')
        cfg = await get_or_create_config_fn(binding["clinic_id"])
        session_id = f"twilio_{call_sid}"
        session = await db.receptionist_sessions.find_one({"session_id": session_id, "clinic_id": binding["clinic_id"]}, {"_id": 0}) or {"transcript": []}
        transcript = session.get("transcript", [])

        if not speech:
            body = (
                '<Say voice="alice">Sorry, I did not hear you. Please leave a brief message after the beep and a human will call you back.</Say>'
                '<Record maxLength="90" action="/api/twilio/voice/voicemail" method="POST"/>'
            )
            return _twiml(body)

        kw = emergency_kw_fn(speech)
        resp = await receptionist_reply_fn(cfg, transcript, speech)
        if kw:
            resp["handoff"] = "urgent"
            resp["emergency_detected"] = True
            resp["reply"] = cfg.get("emergency_instructions", resp.get("reply", ""))

        transcript.append({"role": "user", "text": speech, "at": datetime.now(timezone.utc).isoformat(), "channel": "voice"})
        transcript.append({"role": "assistant", "text": resp.get("reply", ""), "at": datetime.now(timezone.utc).isoformat(),
                           "channel": "voice", "meta": {"handoff": resp.get("handoff"), "emergency": resp.get("emergency_detected", False)}})
        await db.receptionist_sessions.update_one(
            {"session_id": session_id, "clinic_id": binding["clinic_id"]},
            {"$set": {"transcript": transcript, "last_activity": datetime.now(timezone.utc).isoformat(),
                      "handed_off": resp.get("handoff") in ("needed", "urgent")}},
        )

        reply_text = resp.get("reply", "")
        # SSML-escape a few
        reply_text_safe = (reply_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

        if resp.get("handoff") == "urgent":
            body = f'<Say voice="alice">{reply_text_safe}</Say><Hangup/>'
            # Route to staff inbox
            await create_task_fn(db, binding["clinic_id"], None,
                                 title="URGENT — phone caller reported an emergency",
                                 description=f"Caller: {form.get('From','')} · Said: {speech}",
                                 priority="urgent", source="twilio_voice", source_id=call_sid, due_days=0)
        else:
            body = (
                f'<Say voice="alice">{reply_text_safe}</Say>'
                f'<Gather input="speech" action="/api/twilio/voice/gather" method="POST" speechTimeout="auto" timeout="6" language="en-US">'
                f'<Say voice="alice">Anything else?</Say>'
                f'</Gather>'
                f'<Say voice="alice">Thanks for calling. Goodbye.</Say>'
                f'<Hangup/>'
            )
        return _twiml(body)

    @router.post("/voice/voicemail")
    async def voice_voicemail(request: Request):
        form = dict(await request.form())
        if not _validate_signature(request, form):
            raise HTTPException(403, "Invalid Twilio signature")
        to_number = form.get("To", "")
        call_sid = form.get("CallSid", "")
        recording_url = form.get("RecordingUrl", "")
        rec_duration = int(form.get("RecordingDuration", "0") or "0")
        binding = await _clinic_from_number(to_number)
        if not binding:
            return _twiml('<Hangup/>')
        # Log voicemail message and task; transcription is best-effort (Whisper).
        transcript_text = ""
        try:
            if recording_url:
                import httpx, base64
                auth = base64.b64encode(f"{TWILIO_ACCOUNT_SID}:{TWILIO_AUTH_TOKEN}".encode()).decode()
                async with httpx.AsyncClient(timeout=30) as c:
                    r = await c.get(recording_url + ".mp3", headers={"Authorization": f"Basic {auth}"})
                    if r.status_code == 200:
                        transcript_text = await transcribe_audio_fn(r.content, filename="voicemail.mp3")
        except Exception as e:
            logger.warning(f"Voicemail transcription failed: {e}")

        await db.messages.insert_one({
            "id": str(uuid.uuid4()),
            "clinic_id": binding["clinic_id"],
            "received_at": datetime.now(timezone.utc).isoformat(),
            "channel": "Phone voicemail",
            "subject": f"Voicemail from {form.get('From','unknown')}",
            "body": transcript_text or f"Voicemail recording: {recording_url}",
            "status": "new",
            "category": "routine",
            "draft": None,
        })
        await create_task_fn(db, binding["clinic_id"], None,
                             title=f"Return voicemail from {form.get('From','unknown')}",
                             description=(transcript_text or "See recording in Twilio console")[:300],
                             priority="high", source="twilio_voicemail", source_id=call_sid, due_days=0)
        await _log_usage(binding["clinic_id"], "voice", seconds=rec_duration, metadata={"call_sid": call_sid, "voicemail": True})
        return _twiml('<Say voice="alice">Thank you. A staff member will call you back. Goodbye.</Say><Hangup/>')

    @router.post("/voice/status")
    async def voice_status(request: Request):
        """Twilio status callback — meters completed call duration for overage billing."""
        form = dict(await request.form())
        if not _validate_signature(request, form):
            raise HTTPException(403, "Invalid Twilio signature")
        to_number = form.get("To", "")
        call_sid = form.get("CallSid", "")
        call_status = form.get("CallStatus", "")
        duration = int(form.get("CallDuration", "0") or "0")
        binding = await _clinic_from_number(to_number)
        if not binding or call_status != "completed" or duration <= 0:
            return {"ok": True}
        await _log_usage(binding["clinic_id"], "voice", seconds=duration, metadata={"call_sid": call_sid})
        return {"ok": True}

    @router.post("/sms/inbound")
    async def sms_inbound(request: Request):
        form = dict(await request.form())
        if not _validate_signature(request, form):
            raise HTTPException(403, "Invalid Twilio signature")
        to_number = form.get("To", "")
        from_number = form.get("From", "")
        body_in = (form.get("Body") or "").strip()
        binding = await _clinic_from_number(to_number)
        if not binding:
            return _twiml('<Message>This number is not configured.</Message>')
        cfg = await get_or_create_config_fn(binding["clinic_id"])
        session_id = f"sms_{from_number}"
        session = await db.receptionist_sessions.find_one({"session_id": session_id, "clinic_id": binding["clinic_id"]}, {"_id": 0}) or {"transcript": []}
        transcript = session.get("transcript", [])
        kw = emergency_kw_fn(body_in)
        resp = await receptionist_reply_fn(cfg, transcript, body_in)
        if kw:
            resp["handoff"] = "urgent"
            resp["emergency_detected"] = True
            resp["reply"] = cfg.get("emergency_instructions", resp.get("reply", ""))

        transcript.append({"role": "user", "text": body_in, "at": datetime.now(timezone.utc).isoformat(), "channel": "sms"})
        transcript.append({"role": "assistant", "text": resp.get("reply", ""), "at": datetime.now(timezone.utc).isoformat(), "channel": "sms"})
        await db.receptionist_sessions.update_one(
            {"session_id": session_id, "clinic_id": binding["clinic_id"]},
            {"$set": {"clinic_id": binding["clinic_id"], "session_id": session_id, "transcript": transcript,
                      "channel": "sms", "from_number": from_number,
                      "last_activity": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
        if resp.get("handoff") in ("needed", "urgent"):
            await create_task_fn(db, binding["clinic_id"], None,
                                 title=("URGENT SMS — possible emergency" if resp.get("handoff") == "urgent" else f"SMS handoff — {from_number}"),
                                 description=body_in[:400],
                                 priority=("urgent" if resp.get("handoff") == "urgent" else "high"),
                                 source="twilio_sms", source_id=from_number, due_days=0)
        await _log_usage(binding["clinic_id"], "sms", seconds=0, metadata={"from": from_number})
        reply_safe = (resp.get("reply", "") or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return _twiml(f'<Message>{reply_safe}</Message>')

    # ---------- Authenticated: number provisioning + usage ----------
    @router.get("/status")
    async def status_check(user=Depends(auth_dep)):
        cid = user["clinic_id"]
        number = await db.twilio_numbers.find_one({"clinic_id": cid}, {"_id": 0})
        return {"configured": twilio_configured(), "number": number}

    @router.post("/provision")
    async def provision(req: ProvisionReq, user=Depends(auth_dep)):
        """Search for available Twilio numbers and assign one to this clinic."""
        client = _get_twilio_client()
        if not TWILIO_VOICE_WEBHOOK_BASE:
            raise HTTPException(500, "Server is missing PUBLIC_APP_URL — refusing to provision without a public webhook base.")
        cid = user["clinic_id"]
        # Only one number per clinic in MVP
        if await db.twilio_numbers.find_one({"clinic_id": cid}):
            raise HTTPException(400, "This clinic already has a number. Release it first.")
        try:
            search_kwargs = {"sms_enabled": True, "voice_enabled": True, "limit": 5}
            if req.area_code:
                search_kwargs["area_code"] = req.area_code
            available = client.available_phone_numbers("US").local.list(**search_kwargs)
            if not available:
                raise HTTPException(404, "No numbers available for that area code.")
            chosen = available[0]
            base = TWILIO_VOICE_WEBHOOK_BASE.rstrip("/") if TWILIO_VOICE_WEBHOOK_BASE else ""
            purchased = client.incoming_phone_numbers.create(
                phone_number=chosen.phone_number,
                friendly_name=req.friendly_name or f"Vetaura · {cid}",
                voice_url=f"{base}/api/twilio/voice/inbound" if base else None,
                voice_method="POST",
                status_callback=f"{base}/api/twilio/voice/status" if base else None,
                status_callback_method="POST",
                sms_url=f"{base}/api/twilio/sms/inbound" if base else None,
                sms_method="POST",
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Twilio provision failed: {e}")
            raise HTTPException(500, f"Twilio provision failed: {e}")

        doc = {
            "id": str(uuid.uuid4()),
            "clinic_id": cid,
            "phone_sid": purchased.sid,
            "phone_number": purchased.phone_number,
            "friendly_name": purchased.friendly_name,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.twilio_numbers.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.post("/release")
    async def release(req: ReleaseReq, user=Depends(auth_dep)):
        client = _get_twilio_client()
        cid = user["clinic_id"]
        number = await db.twilio_numbers.find_one({"clinic_id": cid, "phone_sid": req.phone_sid})
        if not number:
            raise HTTPException(404, "Number not found for this clinic")
        try:
            client.incoming_phone_numbers(req.phone_sid).delete()
        except Exception as e:
            logger.warning(f"Twilio release warning: {e}")
        await db.twilio_numbers.delete_one({"phone_sid": req.phone_sid, "clinic_id": cid})
        return {"ok": True}

    @router.get("/usage")
    async def usage(user=Depends(auth_dep)):
        cid = user["clinic_id"]
        pipeline = [
            {"$match": {"clinic_id": cid}},
            {"$group": {"_id": "$kind", "seconds": {"$sum": "$seconds"}, "count": {"$sum": 1}}},
        ]
        rows = await db.voice_usage.aggregate(pipeline).to_list(10)
        totals = {r["_id"]: {"seconds": r["seconds"], "count": r["count"]} for r in rows}
        voice_seconds = totals.get("voice", {}).get("seconds", 0)
        sms_count = totals.get("sms", {}).get("count", 0)
        return {
            "voice_seconds": voice_seconds,
            "voice_minutes": round(voice_seconds / 60, 1),
            "sms_count": sms_count,
        }

    return router
