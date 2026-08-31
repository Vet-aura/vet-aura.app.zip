"""Per-clinic secrets & integration credentials.

Design principles (A2P 10DLC / ISV best practice):
  - We NEVER store a clinic's Twilio Auth Token.
  - Outbound calls use a restricted API Key (SID + Secret) the clinic creates for us.
  - Inbound webhooks are secured by a per-clinic random `webhook_token` embedded in the URL.
    The clinic pastes the tokenised URL into their Twilio number/messaging-service config; no
    external caller can spoof it without knowing the token.
  - Every clinic uses a Twilio Messaging Service so all SMS flow through their approved A2P
    Campaign, not arbitrary numbers.

Collections:
  - twilio_credentials: {clinic_id, account_sid, api_key_sid, api_key_secret_encrypted,
                        messaging_service_sid?, webhook_token, friendly_name,
                        verified_at, updated_at}
  - email_credentials:  {clinic_id, provider ('resend'|'sendgrid'), api_key_encrypted,
                        from_email, from_name, verified_at, updated_at}

Never return the raw secret to the client — always masked. Decryption happens in-process
when we need to call the provider.
"""
from __future__ import annotations
import secrets
from datetime import datetime, timezone
from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field, field_validator
from motor.motor_asyncio import AsyncIOMotorDatabase

from crypto_service import encrypt, decrypt, mask


# ---------- Twilio ----------
class TwilioCredsReq(BaseModel):
    account_sid: str = Field(min_length=34, max_length=34, pattern=r"^AC[0-9a-fA-F]{32}$")
    api_key_sid: str = Field(min_length=34, max_length=34, pattern=r"^SK[0-9a-fA-F]{32}$")
    api_key_secret: str = Field(min_length=10, max_length=128)
    messaging_service_sid: Optional[str] = None

    @field_validator("messaging_service_sid")
    @classmethod
    def _valid_msg_svc(cls, v):
        if v in (None, ""):
            return None
        if not v.startswith("MG") or len(v) != 34:
            raise ValueError("Messaging Service SID must start with 'MG' and be 34 chars.")
        return v


async def get_twilio_creds(db: AsyncIOMotorDatabase, clinic_id: str) -> Optional[dict]:
    doc = await db.twilio_credentials.find_one({"clinic_id": clinic_id}, {"_id": 0})
    if not doc:
        return None
    try:
        api_key_secret = decrypt(doc.get("api_key_secret_encrypted", ""))
    except Exception:
        # Corrupt ciphertext (e.g. rotated encryption key or legacy seed) — treat as
        # unconfigured so webhooks return a graceful "not configured" response instead
        # of crashing the request handler.
        return None
    return {
        "clinic_id": doc["clinic_id"],
        "account_sid": doc["account_sid"],
        "api_key_sid": doc["api_key_sid"],
        "api_key_secret": api_key_secret,
        "messaging_service_sid": doc.get("messaging_service_sid"),
        "webhook_token": doc.get("webhook_token"),
        "friendly_name": doc.get("friendly_name"),
        "updated_at": doc.get("updated_at"),
        "verified_at": doc.get("verified_at"),
    }


async def get_twilio_creds_by_token(db: AsyncIOMotorDatabase, clinic_id: str, webhook_token: str) -> Optional[dict]:
    """Route an inbound webhook by tokenised URL. Returns creds only if token matches."""
    creds = await get_twilio_creds(db, clinic_id)
    if not creds:
        return None
    if not creds.get("webhook_token") or not secrets.compare_digest(creds["webhook_token"], webhook_token):
        return None
    return creds


def get_twilio_client_from_creds(creds: dict):
    """Build a Twilio client using the clinic's API Key + Secret bound to their Account SID."""
    from twilio.rest import Client
    return Client(creds["api_key_sid"], creds["api_key_secret"], creds["account_sid"])


# ---------- Email ----------
class EmailCredsReq(BaseModel):
    provider: Literal["resend", "sendgrid"]
    api_key: str = Field(min_length=8, max_length=256)
    from_email: EmailStr
    from_name: Optional[str] = None


async def get_email_creds(db: AsyncIOMotorDatabase, clinic_id: str) -> Optional[dict]:
    doc = await db.email_credentials.find_one({"clinic_id": clinic_id}, {"_id": 0})
    if not doc:
        return None
    return {
        "clinic_id": doc["clinic_id"],
        "provider": doc["provider"],
        "api_key": decrypt(doc.get("api_key_encrypted", "")),
        "from_email": doc.get("from_email"),
        "from_name": doc.get("from_name"),
        "updated_at": doc.get("updated_at"),
        "verified_at": doc.get("verified_at"),
    }


# ---------- Routes ----------
def build_credentials_routes(db: AsyncIOMotorDatabase, auth_dep):
    router = APIRouter(prefix="/api/integrations")

    @router.get("/twilio")
    async def get_twilio(user=Depends(auth_dep)):
        doc = await db.twilio_credentials.find_one({"clinic_id": user["clinic_id"]}, {"_id": 0})
        if not doc:
            return {"connected": False}
        return {
            "connected": True,
            "account_sid_masked": mask(doc["account_sid"], keep=4),
            "api_key_sid_masked": mask(doc["api_key_sid"], keep=4),
            "messaging_service_sid": doc.get("messaging_service_sid"),
            "friendly_name": doc.get("friendly_name"),
            "webhook_token": doc.get("webhook_token"),
            "updated_at": doc.get("updated_at"),
            "verified_at": doc.get("verified_at"),
        }

    @router.post("/twilio")
    async def set_twilio(req: TwilioCredsReq, user=Depends(auth_dep)):
        # Validate live by fetching the account via the API Key auth.
        try:
            from twilio.rest import Client
            client = Client(req.api_key_sid, req.api_key_secret, req.account_sid)
            acct = client.api.accounts(req.account_sid).fetch()
            friendly = acct.friendly_name
            # If a messaging service SID is provided, verify it exists on this account
            if req.messaging_service_sid:
                try:
                    client.messaging.v1.services(req.messaging_service_sid).fetch()
                except Exception as e:
                    raise HTTPException(400, f"Messaging Service SID not found on this account: {e}")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(400, f"Twilio credentials invalid: {e}")

        now = datetime.now(timezone.utc).isoformat()
        existing = await db.twilio_credentials.find_one({"clinic_id": user["clinic_id"]}, {"webhook_token": 1})
        webhook_token = (existing or {}).get("webhook_token") or secrets.token_urlsafe(32)
        await db.twilio_credentials.update_one(
            {"clinic_id": user["clinic_id"]},
            {"$set": {
                "clinic_id": user["clinic_id"],
                "account_sid": req.account_sid,
                "api_key_sid": req.api_key_sid,
                "api_key_secret_encrypted": encrypt(req.api_key_secret),
                "messaging_service_sid": req.messaging_service_sid,
                "friendly_name": friendly,
                "webhook_token": webhook_token,
                "updated_at": now,
                "verified_at": now,
            }},
            upsert=True,
        )
        return {"ok": True, "friendly_name": friendly, "webhook_token": webhook_token, "verified_at": now}

    @router.post("/twilio/rotate-webhook-token")
    async def rotate_webhook_token(user=Depends(auth_dep)):
        token = secrets.token_urlsafe(32)
        r = await db.twilio_credentials.update_one(
            {"clinic_id": user["clinic_id"]},
            {"$set": {"webhook_token": token, "updated_at": datetime.now(timezone.utc).isoformat()}},
        )
        if r.matched_count == 0:
            raise HTTPException(404, "Connect Twilio first.")
        return {"webhook_token": token}

    @router.delete("/twilio")
    async def delete_twilio(user=Depends(auth_dep)):
        await db.twilio_numbers.delete_many({"clinic_id": user["clinic_id"]})
        await db.twilio_credentials.delete_one({"clinic_id": user["clinic_id"]})
        return {"ok": True}

    @router.get("/email")
    async def get_email(user=Depends(auth_dep)):
        doc = await db.email_credentials.find_one({"clinic_id": user["clinic_id"]}, {"_id": 0})
        if not doc:
            return {"connected": False}
        enc = doc.get("api_key_encrypted", "")
        return {
            "connected": True,
            "provider": doc["provider"],
            "from_email": doc.get("from_email"),
            "from_name": doc.get("from_name"),
            "api_key_masked": "•" * 8 + (enc[-6:] if enc else ""),
            "updated_at": doc.get("updated_at"),
            "verified_at": doc.get("verified_at"),
        }

    @router.post("/email")
    async def set_email(req: EmailCredsReq, user=Depends(auth_dep)):
        # Best-effort validation: call a low-privilege endpoint.
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as c:
                if req.provider == "resend":
                    r = await c.get("https://api.resend.com/domains", headers={"Authorization": f"Bearer {req.api_key}"})
                else:
                    r = await c.get("https://api.sendgrid.com/v3/user/profile", headers={"Authorization": f"Bearer {req.api_key}"})
                if r.status_code >= 400:
                    raise HTTPException(400, f"{req.provider.title()} rejected the API key ({r.status_code}). Check the key and try again.")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(400, f"Could not reach {req.provider}: {e}")
        now = datetime.now(timezone.utc).isoformat()
        await db.email_credentials.update_one(
            {"clinic_id": user["clinic_id"]},
            {"$set": {
                "clinic_id": user["clinic_id"],
                "provider": req.provider,
                "api_key_encrypted": encrypt(req.api_key),
                "from_email": req.from_email,
                "from_name": req.from_name or "",
                "updated_at": now,
                "verified_at": now,
            }},
            upsert=True,
        )
        return {"ok": True, "verified_at": now}

    @router.delete("/email")
    async def delete_email(user=Depends(auth_dep)):
        await db.email_credentials.delete_one({"clinic_id": user["clinic_id"]})
        return {"ok": True}

    return router
