"""Email delivery abstraction using per-clinic BYOK.

Supports Resend and SendGrid. All sends go through the clinic's own API key + from-address
so bounces and deliverability sit with the clinic (not Vetaura).
"""
from __future__ import annotations
import logging
from typing import Optional
import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase
from credentials_service import get_email_creds

logger = logging.getLogger(__name__)


class EmailNotConfigured(Exception):
    pass


class EmailSendFailed(Exception):
    pass


async def send_email(db: AsyncIOMotorDatabase, clinic_id: str, *,
                     to: list[str] | str, subject: str,
                     html: Optional[str] = None, text: Optional[str] = None,
                     reply_to: Optional[str] = None) -> dict:
    creds = await get_email_creds(db, clinic_id)
    if not creds:
        raise EmailNotConfigured("Clinic has not connected an email provider.")
    if isinstance(to, str):
        to = [to]
    from_email = creds["from_email"]
    from_name = creds.get("from_name") or ""
    from_field = f"{from_name} <{from_email}>" if from_name else from_email

    async with httpx.AsyncClient(timeout=20) as c:
        if creds["provider"] == "resend":
            payload = {
                "from": from_field,
                "to": to,
                "subject": subject,
                "html": html or f"<p>{text or ''}</p>",
                "text": text or "",
            }
            if reply_to:
                payload["reply_to"] = reply_to
            r = await c.post("https://api.resend.com/emails",
                             headers={"Authorization": f"Bearer {creds['api_key']}",
                                      "Content-Type": "application/json"},
                             json=payload)
            if r.status_code >= 400:
                raise EmailSendFailed(f"Resend {r.status_code}: {r.text[:300]}")
            return r.json()
        else:
            # SendGrid v3
            data = {
                "personalizations": [{"to": [{"email": e} for e in to], "subject": subject}],
                "from": {"email": from_email, "name": from_name or from_email},
                "content": [
                    {"type": "text/plain", "value": text or " "},
                    {"type": "text/html", "value": html or f"<p>{text or ''}</p>"},
                ],
            }
            if reply_to:
                data["reply_to"] = {"email": reply_to}
            r = await c.post("https://api.sendgrid.com/v3/mail/send",
                             headers={"Authorization": f"Bearer {creds['api_key']}",
                                      "Content-Type": "application/json"},
                             json=data)
            if r.status_code >= 400:
                raise EmailSendFailed(f"SendGrid {r.status_code}: {r.text[:300]}")
            return {"ok": True, "provider": "sendgrid"}
