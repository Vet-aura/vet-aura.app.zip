"""Platform-level lead notifications (demo requests, Try-it demos, new clinic signups).

Clinic email is BYOK, but leads belong to Vetaura itself, so this uses an optional
platform Resend key. If the env vars are not set, leads are still stored in MongoDB
and listed at GET /api/admin/leads; nothing fails.

Env:
  LEADS_NOTIFY_EMAIL      where lead alerts go (e.g. vetaura.app@gmail.com)
  PLATFORM_RESEND_API_KEY Resend API key for the vet-aura.com sending domain
  PLATFORM_FROM_EMAIL     verified sender, e.g. "Vetaura <notify@vet-aura.com>"
"""
from __future__ import annotations
import html
import logging
import os
import hmac
from typing import Optional

import httpx
from fastapi import APIRouter, Header, HTTPException

logger = logging.getLogger(__name__)


async def notify_lead(kind: str, fields: dict) -> None:
    """Best-effort email alert. Never raises."""
    to = os.environ.get("LEADS_NOTIFY_EMAIL", "").strip()
    key = os.environ.get("PLATFORM_RESEND_API_KEY", "").strip()
    sender = os.environ.get("PLATFORM_FROM_EMAIL", "").strip()
    if not (to and key and sender):
        logger.info(f"Lead stored ({kind}); email alert skipped (platform email not configured).")
        return
    rows = "".join(
        f"<tr><td style='padding:4px 12px 4px 0;color:#555'>{html.escape(str(k))}</td>"
        f"<td style='padding:4px 0'>{html.escape(str(v or ''))}</td></tr>"
        for k, v in fields.items()
    )
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "from": sender,
                    "to": [to],
                    "subject": f"New Vetaura lead: {kind}",
                    "html": f"<h3>New {html.escape(kind)}</h3><table>{rows}</table>",
                    "reply_to": fields.get("email") or None,
                },
            )
            if r.status_code >= 400:
                logger.warning(f"Lead email failed: {r.status_code} {r.text[:200]}")
    except Exception as e:  # pragma: no cover - network best effort
        logger.warning(f"Lead email failed: {e}")


def build_admin_lead_routes(db):
    router = APIRouter(prefix="/api/admin")

    def _check(token: Optional[str]):
        admin = os.environ.get("VETAURA_ADMIN_TOKEN", "")
        if not admin or not token or not hmac.compare_digest(token, admin):
            raise HTTPException(403, "Admin token required")

    @router.get("/leads")
    async def list_leads(x_admin_token: Optional[str] = Header(None)):
        """All demo requests, Try-it demos and signups, newest first."""
        _check(x_admin_token)
        demos = await db.demo_requests.find({}, {"_id": 0}).sort("at", -1).to_list(1000)
        tryit = await db.tryit_leads.find({}, {"_id": 0, "profile": 0}).sort("created_at", -1).to_list(1000)
        clinics = await db.clinics.find(
            {"plan": {"$ne": "demo"}, "clinic_id": {"$ne": "demo"}},
            {"_id": 0, "clinic_id": 1, "name": 1, "owner_email": 1, "plan": 1, "plan_status": 1, "created_at": 1},
        ).sort("created_at", -1).to_list(1000)
        return {"demo_requests": demos, "tryit_demos": tryit, "clinics": clinics}

    return router
