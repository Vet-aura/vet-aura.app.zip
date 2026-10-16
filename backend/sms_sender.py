"""Thin outbound SMS helper through the clinic's own Twilio Messaging Service (BYOK)."""
import asyncio
import uuid
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase
from credentials_service import get_twilio_creds, get_twilio_client_from_creds


async def send_raw_sms(db: AsyncIOMotorDatabase, clinic_id: str, to: str, body: str, kind: str, **meta) -> str:
    """Send via the clinic's Messaging Service and log usage. Returns the message SID; raises on failure."""
    creds = await get_twilio_creds(db, clinic_id)
    if not creds or not creds.get("messaging_service_sid"):
        raise RuntimeError("Twilio Messaging Service is not connected.")
    client = get_twilio_client_from_creds(creds)
    msg = await asyncio.to_thread(client.messages.create, messaging_service_sid=creds["messaging_service_sid"],
                                  to=to, body=body[:1590])
    await db.voice_usage.insert_one({"id": str(uuid.uuid4()), "clinic_id": clinic_id, "kind": "sms", "seconds": 0,
                                     "metadata": {"to": to, "sid": msg.sid, "type": kind, **meta},
                                     "at": datetime.now(timezone.utc).isoformat()})
    return msg.sid
