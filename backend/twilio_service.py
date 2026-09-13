"""Twilio Voice + SMS webhooks — per-clinic BYOK (bring-your-own-keys).

Compliance model: Vetaura is a pure orchestrator. Each clinic owns its Twilio account,
creates a RESTRICTED API KEY, and pastes it into Vetaura. Inbound webhooks are addressed
by a tokenised per-clinic URL:

    /api/twilio/voice/inbound/{clinic_id}/{webhook_token}
    /api/twilio/sms/inbound/{clinic_id}/{webhook_token}
    /api/twilio/voice/gather/{clinic_id}/{webhook_token}
    /api/twilio/voice/voicemail/{clinic_id}/{webhook_token}
    /api/twilio/voice/status/{clinic_id}/{webhook_token}

The clinic pastes these URLs into their Twilio number/messaging-service config in the
Twilio Console. Because the token is random per clinic and known only to the clinic and
Vetaura, no outside caller can spoof requests. We also require the incoming To=/From=
fields to correspond to a Twilio number registered to the clinic.

Outbound API calls (provisioning, SMS sends) use the clinic's API-Key-based client.
"""
from __future__ import annotations
import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Depends, Response
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorDatabase

from credentials_service import get_twilio_creds, get_twilio_creds_by_token, get_twilio_client_from_creds
from sms_compliance import (
    is_stop_message, is_help_message, is_start_message, STOP_ACK,
    record_consent_transition, has_active_consent, build_help_reply, can_send_sms,
)

logger = logging.getLogger(__name__)

TWILIO_VOICE_WEBHOOK_BASE = os.environ.get("PUBLIC_APP_URL", "")


def _public_url_for_signature(request: Request) -> str:
    """Reconstruct the URL Twilio would have signed, using X-Forwarded-Proto/Host from the
    proxy. Twilio signs the PUBLIC URL, not the internal container URL FastAPI sees."""
    fwd_proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    fwd_host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    path = request.url.path
    q = request.url.query
    return f"{fwd_proto}://{fwd_host}{path}" + (f"?{q}" if q else "")


def _validate_twilio_signature(request: Request, form: dict, auth_token: str) -> bool:
    """Validate X-Twilio-Signature. Returns True if signature is valid OR if the clinic
    has not stored an auth_token (best-effort — path token still gates the request)."""
    if not auth_token:
        return True  # Path token is the gate when clinic didn't supply an auth token.
    sig = request.headers.get("X-Twilio-Signature", "")
    if not sig:
        return False
    try:
        from twilio.request_validator import RequestValidator
        validator = RequestValidator(auth_token)
        return validator.validate(_public_url_for_signature(request), form, sig)
    except Exception as e:
        logger.warning(f"Twilio signature validator failed: {e}")
        return False


TWILIO_RECORDING_HOSTS = {"api.twilio.com"}


def _is_twilio_recording_url(url: str) -> bool:
    from urllib.parse import urlparse
    try:
        p = urlparse(url)
    except Exception:
        return False
    if p.scheme != "https":
        return False
    host = (p.hostname or "").lower()
    return host in TWILIO_RECORDING_HOSTS


def _twiml(body: str) -> Response:
    xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<Response>{body}</Response>'
    return Response(content=xml, media_type="application/xml")


def _escape(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class ProvisionReq(BaseModel):
    area_code: Optional[str] = None
    friendly_name: Optional[str] = None


class ReleaseReq(BaseModel):
    phone_sid: str


class OutboundSmsReq(BaseModel):
    phone_e164: str
    body: str
    message_type: str = "care"   # 'care' or 'marketing'


def build_twilio_routes(db: AsyncIOMotorDatabase, auth_dep,
                        receptionist_reply_fn, get_or_create_config_fn,
                        emergency_kw_fn, create_task_fn, transcribe_audio_fn):
    router = APIRouter(prefix="/api/twilio")

    async def _log_usage(clinic_id: str, kind: str, seconds: int = 0, metadata: dict | None = None):
        await db.voice_usage.insert_one({
            "id": str(uuid.uuid4()),
            "clinic_id": clinic_id,
            "kind": kind,
            "seconds": int(seconds or 0),
            "metadata": metadata or {},
            "at": datetime.now(timezone.utc).isoformat(),
        })

    async def _load_ctx(clinic_id: str, webhook_token: str, form: dict, request: Optional[Request] = None) -> Optional[dict]:
        """Validate token, optional Twilio signature, and return {creds, binding, cfg}."""
        creds = await get_twilio_creds_by_token(db, clinic_id, webhook_token)
        if not creds:
            return None
        # Enforce X-Twilio-Signature if the clinic has provided an auth token.
        if request is not None and creds.get("auth_token"):
            if not _validate_twilio_signature(request, form, creds["auth_token"]):
                logger.warning(f"Rejected inbound webhook — invalid signature for clinic {clinic_id}")
                return None
        to_number = form.get("To", "")
        binding = await db.twilio_numbers.find_one({"clinic_id": clinic_id, "phone_number": to_number}, {"_id": 0})
        if not binding:
            return None
        cfg = await get_or_create_config_fn(clinic_id)
        return {"creds": creds, "binding": binding, "cfg": cfg}

    # ---------------- Public webhooks ----------------
    @router.post("/voice/inbound/{clinic_id}/{webhook_token}")
    async def voice_inbound(clinic_id: str, webhook_token: str, request: Request):
        form = dict(await request.form())
        ctx = await _load_ctx(clinic_id, webhook_token, form, request)
        if not ctx:
            return _twiml('<Say voice="alice">This number is not configured. Goodbye.</Say><Hangup/>')

        cfg = ctx["cfg"]
        call_sid = form.get("CallSid", "")
        from_number = form.get("From", "")
        greeting = cfg.get("greeting") or f"Thank you for calling {cfg.get('clinic_name', 'our clinic')}."
        session_id = f"twilio_{call_sid}"
        await db.receptionist_sessions.update_one(
            {"session_id": session_id, "clinic_id": clinic_id},
            {"$setOnInsert": {
                "session_id": session_id, "clinic_id": clinic_id,
                "transcript": [], "created_at": datetime.now(timezone.utc).isoformat(),
                "channel": "voice", "from_number": from_number, "call_sid": call_sid,
                "status": "active", "handed_off": False,
            }},
            upsert=True,
        )
        gather = f"/api/twilio/voice/gather/{clinic_id}/{webhook_token}"
        vm = f"/api/twilio/voice/voicemail/{clinic_id}/{webhook_token}"
        body = (
            f'<Say voice="alice">{_escape(greeting)}</Say>'
            f'<Gather input="speech" action="{gather}" method="POST" speechTimeout="auto" timeout="6" language="en-US">'
            f'<Say voice="alice">How can I help you today?</Say>'
            f'</Gather>'
            f'<Say voice="alice">I did not catch that. Please leave a message after the beep.</Say>'
            f'<Record maxLength="90" action="{vm}" method="POST"/>'
        )
        return _twiml(body)

    @router.post("/voice/gather/{clinic_id}/{webhook_token}")
    async def voice_gather(clinic_id: str, webhook_token: str, request: Request):
        form = dict(await request.form())
        ctx = await _load_ctx(clinic_id, webhook_token, form, request)
        if not ctx:
            return _twiml('<Hangup/>')
        cfg = ctx["cfg"]
        call_sid = form.get("CallSid", "")
        speech = (form.get("SpeechResult") or "").strip()
        session_id = f"twilio_{call_sid}"
        session = await db.receptionist_sessions.find_one({"session_id": session_id, "clinic_id": clinic_id}, {"_id": 0}) or {"transcript": []}
        transcript = session.get("transcript", [])
        gather = f"/api/twilio/voice/gather/{clinic_id}/{webhook_token}"
        vm = f"/api/twilio/voice/voicemail/{clinic_id}/{webhook_token}"

        if not speech:
            return _twiml(f'<Say voice="alice">Sorry, I did not hear you. Please leave a brief message after the beep.</Say><Record maxLength="90" action="{vm}" method="POST"/>')

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
            {"session_id": session_id, "clinic_id": clinic_id},
            {"$set": {"transcript": transcript, "last_activity": datetime.now(timezone.utc).isoformat(),
                      "handed_off": resp.get("handoff") in ("needed", "urgent")}},
        )

        reply_safe = _escape(resp.get("reply", ""))
        if resp.get("handoff") == "urgent":
            await create_task_fn(db, clinic_id, None,
                                 title="URGENT — phone caller reported an emergency",
                                 description=f"Caller: {form.get('From','')} · Said: {speech}",
                                 priority="urgent", source="twilio_voice", source_id=call_sid, due_days=0)
            return _twiml(f'<Say voice="alice">{reply_safe}</Say><Hangup/>')
        return _twiml(
            f'<Say voice="alice">{reply_safe}</Say>'
            f'<Gather input="speech" action="{gather}" method="POST" speechTimeout="auto" timeout="6" language="en-US">'
            f'<Say voice="alice">Anything else?</Say>'
            f'</Gather>'
            f'<Say voice="alice">Thanks for calling. Goodbye.</Say><Hangup/>'
        )

    @router.post("/voice/voicemail/{clinic_id}/{webhook_token}")
    async def voice_voicemail(clinic_id: str, webhook_token: str, request: Request):
        form = dict(await request.form())
        ctx = await _load_ctx(clinic_id, webhook_token, form, request)
        if not ctx:
            return _twiml('<Hangup/>')
        call_sid = form.get("CallSid", "")
        recording_url = form.get("RecordingUrl", "")
        rec_duration = int(form.get("RecordingDuration", "0") or "0")

        transcript_text = ""
        try:
            # SSRF guard: only fetch recordings from api.twilio.com. Never send the clinic's
            # API-Key credentials to an attacker-supplied host.
            if recording_url and _is_twilio_recording_url(recording_url):
                import httpx, base64
                creds = ctx["creds"]
                auth = base64.b64encode(f"{creds['api_key_sid']}:{creds['api_key_secret']}".encode()).decode()
                async with httpx.AsyncClient(timeout=30, follow_redirects=False) as c:
                    r = await c.get(recording_url + ".mp3", headers={"Authorization": f"Basic {auth}"})
                    if r.status_code == 200:
                        transcript_text = await transcribe_audio_fn(r.content, filename="voicemail.mp3")
            elif recording_url:
                logger.warning(f"Voicemail recording URL rejected (non-Twilio host): {recording_url[:100]}")
        except Exception as e:
            logger.warning(f"Voicemail transcription failed: {e}")

        await db.messages.insert_one({
            "id": str(uuid.uuid4()),
            "clinic_id": clinic_id,
            "received_at": datetime.now(timezone.utc).isoformat(),
            "channel": "Phone voicemail",
            "subject": f"Voicemail from {form.get('From','unknown')}",
            "body": transcript_text or f"Voicemail recording: {recording_url}",
            "status": "new",
            "category": "routine",
            "draft": None,
        })
        await create_task_fn(db, clinic_id, None,
                             title=f"Return voicemail from {form.get('From','unknown')}",
                             description=(transcript_text or "See recording in Twilio console")[:300],
                             priority="high", source="twilio_voicemail", source_id=call_sid, due_days=0)
        await _log_usage(clinic_id, "voice", seconds=rec_duration, metadata={"call_sid": call_sid, "voicemail": True})
        return _twiml('<Say voice="alice">Thank you. A staff member will call you back. Goodbye.</Say><Hangup/>')

    @router.post("/voice/status/{clinic_id}/{webhook_token}")
    async def voice_status(clinic_id: str, webhook_token: str, request: Request):
        form = dict(await request.form())
        ctx = await _load_ctx(clinic_id, webhook_token, form, request)
        if not ctx:
            return {"ok": False}
        call_sid = form.get("CallSid", "")
        call_status = form.get("CallStatus", "")
        duration = int(form.get("CallDuration", "0") or "0")
        if call_status == "completed" and duration > 0:
            await _log_usage(clinic_id, "voice", seconds=duration, metadata={"call_sid": call_sid})
        return {"ok": True}

    @router.post("/sms/inbound/{clinic_id}/{webhook_token}")
    async def sms_inbound(clinic_id: str, webhook_token: str, request: Request):
        form = dict(await request.form())
        ctx = await _load_ctx(clinic_id, webhook_token, form, request)
        if not ctx:
            return _twiml('<Message>This number is not configured.</Message>')
        cfg = ctx["cfg"]
        from_number = form.get("From", "")
        body_in = (form.get("Body") or "").strip()

        # 1) STOP / HELP / START — deterministic, must run BEFORE any AI.
        profile = await db.sms_compliance_profiles.find_one({"clinic_id": clinic_id}) or {}
        clinic_name = cfg.get("clinic_name", "Our clinic")
        if is_stop_message(body_in):
            # Opt out of BOTH consent types when a keyword STOP is received.
            for ct in ("care", "marketing"):
                await record_consent_transition(db, clinic_id, from_number, ct, "opt_out",
                                                source="sms_keyword_stop", disclosure_version="",
                                                actor="twilio_inbound", notes=f"body: {body_in[:60]}")
            await _log_usage(clinic_id, "sms", metadata={"from": from_number, "keyword": "STOP"})
            return _twiml(f'<Message>{_escape(STOP_ACK)}</Message>')
        if is_help_message(body_in):
            reply = build_help_reply(profile, clinic_name)
            await _log_usage(clinic_id, "sms", metadata={"from": from_number, "keyword": "HELP"})
            return _twiml(f'<Message>{_escape(reply)}</Message>')
        if is_start_message(body_in):
            await record_consent_transition(db, clinic_id, from_number, "care", "opt_in",
                                            source="sms_keyword_start", disclosure_version="",
                                            actor="twilio_inbound", notes=f"body: {body_in[:60]}")
            await _log_usage(clinic_id, "sms", metadata={"from": from_number, "keyword": "START"})
            return _twiml(f'<Message>{_escape(clinic_name)}: You are resubscribed to appointment reminders and care updates. Reply STOP to opt out at any time.</Message>')

        # 2) AI reply — if no prior consent AND no prior STOP, auto-opt-in from client-initiated inbound.
        prior_stop = await db.consent_events.find_one({
            "clinic_id": clinic_id, "phone_e164": from_number,
            "consent_type": "care", "action": "opt_out"
        })
        if not prior_stop and not await has_active_consent(db, clinic_id, from_number, "care"):
            await record_consent_transition(db, clinic_id, from_number, "care", "opt_in",
                                            source="sms_client_initiated", disclosure_version="inbound_reply_v1",
                                            actor="twilio_inbound", notes="Auto-opt-in from client-initiated inbound.")

        session_id = f"sms_{from_number}"
        session = await db.receptionist_sessions.find_one({"session_id": session_id, "clinic_id": clinic_id}, {"_id": 0}) or {"transcript": []}
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
            {"session_id": session_id, "clinic_id": clinic_id},
            {"$set": {"clinic_id": clinic_id, "session_id": session_id, "transcript": transcript,
                      "channel": "sms", "from_number": from_number,
                      "last_activity": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
        if resp.get("handoff") in ("needed", "urgent"):
            await create_task_fn(db, clinic_id, None,
                                 title=("URGENT SMS — possible emergency" if resp.get("handoff") == "urgent" else f"SMS handoff — {from_number}"),
                                 description=body_in[:400],
                                 priority=("urgent" if resp.get("handoff") == "urgent" else "high"),
                                 source="twilio_sms", source_id=from_number, due_days=0)
        await _log_usage(clinic_id, "sms", metadata={"from": from_number})
        reply_safe = _escape(resp.get("reply", ""))
        # Always append a compliant sender identifier + opt-out footer on outbound care SMS.
        footer = f" — {clinic_name}. Reply STOP to opt out."
        # avoid busting Twilio's 1600-char SMS body limit
        content = (reply_safe[:1400] + footer)[:1590]
        return _twiml(f'<Message>{content}</Message>')

    # ---------------- Authenticated: status + number mgmt + outbound send ----------------
    @router.get("/status")
    async def status_check(user=Depends(auth_dep)):
        cid = user["clinic_id"]
        creds = await db.twilio_credentials.find_one({"clinic_id": cid}, {"_id": 0})
        number = await db.twilio_numbers.find_one({"clinic_id": cid}, {"_id": 0})
        base = TWILIO_VOICE_WEBHOOK_BASE.rstrip("/") if TWILIO_VOICE_WEBHOOK_BASE else ""
        webhooks = None
        if creds and creds.get("webhook_token") and base:
            tok = creds["webhook_token"]
            webhooks = {
                "voice_url": f"{base}/api/twilio/voice/inbound/{cid}/{tok}",
                "voice_status_callback": f"{base}/api/twilio/voice/status/{cid}/{tok}",
                "sms_url": f"{base}/api/twilio/sms/inbound/{cid}/{tok}",
            }
        return {
            "connected": bool(creds),
            "number": number,
            "messaging_service_sid": creds.get("messaging_service_sid") if creds else None,
            "webhooks": webhooks,
        }

    @router.post("/provision")
    async def provision(req: ProvisionReq, user=Depends(auth_dep)):
        """Search for available Twilio numbers on the CLINIC'S OWN Twilio account and assign one."""
        cid = user["clinic_id"]
        creds = await get_twilio_creds(db, cid)
        if not creds:
            raise HTTPException(400, "Connect your Twilio account first.")
        if not TWILIO_VOICE_WEBHOOK_BASE:
            raise HTTPException(500, "Server is missing PUBLIC_APP_URL; cannot configure webhooks.")
        if await db.twilio_numbers.find_one({"clinic_id": cid}):
            raise HTTPException(400, "This clinic already has a number. Release it first.")
        try:
            client = get_twilio_client_from_creds(creds)
            search_kwargs = {"sms_enabled": True, "voice_enabled": True, "limit": 5}
            if req.area_code:
                search_kwargs["area_code"] = req.area_code
            available = client.available_phone_numbers("US").local.list(**search_kwargs)
            if not available:
                raise HTTPException(404, "No numbers available for that area code.")
            chosen = available[0]
            base = TWILIO_VOICE_WEBHOOK_BASE.rstrip("/")
            tok = creds["webhook_token"]
            purchased = client.incoming_phone_numbers.create(
                phone_number=chosen.phone_number,
                friendly_name=req.friendly_name or f"Vetaura · {cid}",
                voice_url=f"{base}/api/twilio/voice/inbound/{cid}/{tok}",
                voice_method="POST",
                status_callback=f"{base}/api/twilio/voice/status/{cid}/{tok}",
                status_callback_method="POST",
                sms_url=f"{base}/api/twilio/sms/inbound/{cid}/{tok}",
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
        cid = user["clinic_id"]
        creds = await get_twilio_creds(db, cid)
        if not creds:
            raise HTTPException(400, "Connect your Twilio account first.")
        number = await db.twilio_numbers.find_one({"clinic_id": cid, "phone_sid": req.phone_sid})
        if not number:
            raise HTTPException(404, "Number not found for this clinic")
        try:
            client = get_twilio_client_from_creds(creds)
            client.incoming_phone_numbers(req.phone_sid).delete()
        except Exception as e:
            logger.warning(f"Twilio release warning: {e}")
        await db.twilio_numbers.delete_one({"phone_sid": req.phone_sid, "clinic_id": cid})
        return {"ok": True}

    @router.post("/sms/send")
    async def send_sms(req: OutboundSmsReq, user=Depends(auth_dep)):
        cid = user["clinic_id"]
        if req.message_type not in ("care", "marketing"):
            raise HTTPException(400, "message_type must be 'care' or 'marketing'")
        allowed, reason = await can_send_sms(db, cid, req.phone_e164, req.message_type)
        if not allowed:
            raise HTTPException(400, f"SMS blocked: {reason}")
        creds = await get_twilio_creds(db, cid)
        if not creds or not creds.get("messaging_service_sid"):
            raise HTTPException(400, "Messaging Service is not connected.")
        try:
            client = get_twilio_client_from_creds(creds)
            cfg = await get_or_create_config_fn(cid)
            clinic_name = cfg.get("clinic_name", "Our clinic")
            body = (req.body or "").strip()[:1400] + f" — {clinic_name}. Reply STOP to opt out."
            msg = client.messages.create(
                messaging_service_sid=creds["messaging_service_sid"],
                to=req.phone_e164,
                body=body,
            )
            await _log_usage(cid, "sms", metadata={"to": req.phone_e164, "sid": msg.sid, "type": req.message_type})
            return {"ok": True, "sid": msg.sid, "status": msg.status}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, f"Twilio send failed: {e}")

    @router.get("/usage")
    async def usage(user=Depends(auth_dep)):
        cid = user["clinic_id"]
        rows = await db.voice_usage.aggregate([
            {"$match": {"clinic_id": cid}},
            {"$group": {"_id": "$kind", "seconds": {"$sum": "$seconds"}, "count": {"$sum": 1}}},
        ]).to_list(10)
        totals = {r["_id"]: {"seconds": r["seconds"], "count": r["count"]} for r in rows}
        voice_seconds = totals.get("voice", {}).get("seconds", 0)
        sms_count = totals.get("sms", {}).get("count", 0)
        return {"voice_seconds": voice_seconds, "voice_minutes": round(voice_seconds / 60, 1), "sms_count": sms_count}

    return router
