"""Brute-force protection for login/signup: per-email lockouts, per-IP throttling, audit + alerts."""
from __future__ import annotations
import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

WINDOW = timedelta(minutes=15)
LOCKOUT = timedelta(minutes=15)
EMAIL_MAX_FAILURES = 5
IP_MAX_ATTEMPTS = 20


TRUSTED_PROXY_HOPS = 2  # Cloudflare + Google LB append the last two X-Forwarded-For entries


def client_ip(request: Request) -> str:
    """Rightmost untrusted X-Forwarded-For hop; client-supplied leading entries are ignored."""
    hops = [h.strip() for h in request.headers.get("x-forwarded-for", "").split(",") if h.strip()]
    if hops:
        return hops[max(0, len(hops) - TRUSTED_PROXY_HOPS - 1)]
    return request.client.host if request.client else "unknown"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class LoginGuard:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def ensure_indexes(self):
        await self.db.login_attempts.create_index("at", expireAfterSeconds=3600)
        await self.db.login_attempts.create_index([("identifier", 1), ("action", 1), ("at", -1)])
        await self.db.login_lockouts.create_index("until", expireAfterSeconds=0)
        await self.db.login_lockouts.create_index("identifier", unique=True)
        await self.db.auth_audit.create_index([("clinic_id", 1), ("at", -1)])
        await self.db.security_alerts.create_index([("clinic_id", 1), ("at", -1)])

    async def audit(self, event: str, email: str, request: Request, user: Optional[dict] = None, **extra):
        await self.db.auth_audit.insert_one({
            "id": str(uuid.uuid4()), "event": event, "email": email,
            "ip": client_ip(request), "user_agent": request.headers.get("user-agent", "")[:300],
            "clinic_id": (user or {}).get("clinic_id"), "at": _now().isoformat(), **extra,
        })

    async def check(self, email: str, request: Request, action: str):
        """Raise 423 if the email is locked, 429 if the IP is over its attempt budget."""
        now = _now()
        lock = await self.db.login_lockouts.find_one({"identifier": f"email:{email}"})
        if lock and _aware(lock["until"]) > now:
            secs = int((_aware(lock["until"]) - now).total_seconds())
            await self.audit(f"{action}_blocked_locked", email, request)
            raise HTTPException(423, f"Too many failed attempts. Try again in {max(1, secs // 60 + 1)} minutes.",
                                headers={"Retry-After": str(secs)})
        ip = client_ip(request)
        count = await self.db.login_attempts.count_documents(
            {"identifier": f"ip:{ip}", "action": action, "at": {"$gte": now - WINDOW}})
        if count >= IP_MAX_ATTEMPTS:
            await self.audit(f"{action}_blocked_ip", email, request)
            raise HTTPException(429, "Too many attempts from this network. Please wait 15 minutes and try again.",
                                headers={"Retry-After": str(int(WINDOW.total_seconds()))})

    async def record_attempt(self, email: str, request: Request, action: str):
        now = _now()
        await self.db.login_attempts.insert_many([
            {"identifier": f"ip:{client_ip(request)}", "action": action, "at": now},
            {"identifier": f"email:{email}", "action": action, "at": now},
        ])

    async def record_login_failure(self, email: str, request: Request, user: Optional[dict]):
        await self.record_attempt(email, request, "login")
        await self.audit("login_failed", email, request, user)
        now = _now()
        fails = await self.db.login_attempts.count_documents(
            {"identifier": f"email:{email}", "action": "login", "at": {"$gte": now - WINDOW}})
        if fails < EMAIL_MAX_FAILURES:
            return
        await self.db.login_lockouts.update_one(
            {"identifier": f"email:{email}"},
            {"$set": {"identifier": f"email:{email}", "until": now + LOCKOUT, "locked_at": now}}, upsert=True)
        await self.db.login_attempts.delete_many({"identifier": f"email:{email}", "action": "login"})
        await self.audit("account_locked", email, request, user, failed_attempts=fails)
        if user:
            await self._alert(user, email, request, fails)

    async def record_login_success(self, email: str, request: Request, user: dict):
        await self.db.login_attempts.delete_many({"identifier": f"email:{email}", "action": "login"})
        await self.audit("login_success", email, request, user)

    async def _alert(self, user: dict, email: str, request: Request, fails: int):
        alert = {
            "id": str(uuid.uuid4()), "clinic_id": user["clinic_id"], "type": "account_lockout",
            "email": email, "ip": client_ip(request), "user_agent": request.headers.get("user-agent", "")[:300],
            "failed_attempts": fails, "locked_until": (_now() + LOCKOUT).isoformat(),
            "at": _now().isoformat(), "acknowledged": False,
        }
        await self.db.security_alerts.insert_one({**alert})
        asyncio.create_task(self._email_owner(alert))

    async def _email_owner(self, alert: dict):
        from email_service import send_email
        clinic = await self.db.clinics.find_one({"clinic_id": alert["clinic_id"]}, {"_id": 0}) or {}
        owner = clinic.get("owner_email")
        if not owner:
            return
        try:
            await send_email(
                self.db, alert["clinic_id"], to=owner,
                subject=f"Security alert: {alert['email']} was locked out of Vetaura",
                text=(f"{alert['failed_attempts']} failed sign-in attempts were made on {alert['email']} "
                      f"from IP {alert['ip']}. The account is locked for 15 minutes "
                      f"(until {alert['locked_until']}). If this wasn't your team, review Settings → Security alerts."),
            )
        except Exception as e:
            logger.info(f"Lockout alert email not sent for clinic {alert['clinic_id']}: {e}")


def build_security_routes(db: AsyncIOMotorDatabase, auth_dep):
    router = APIRouter(prefix="/api/security")

    def _owner(user: dict):
        if user.get("role", "owner") != "owner":
            raise HTTPException(403, "Only clinic owners can view security alerts.")

    @router.get("/alerts")
    async def list_alerts(user=Depends(auth_dep)):
        _owner(user)
        return await db.security_alerts.find({"clinic_id": user["clinic_id"]}, {"_id": 0}).sort("at", -1).to_list(100)

    @router.post("/alerts/{alert_id}/ack")
    async def ack_alert(alert_id: str, user=Depends(auth_dep)):
        _owner(user)
        r = await db.security_alerts.update_one(
            {"id": alert_id, "clinic_id": user["clinic_id"]},
            {"$set": {"acknowledged": True, "acknowledged_by": user["email"], "acknowledged_at": _now().isoformat()}})
        if not r.matched_count:
            raise HTTPException(404, "Alert not found")
        return {"ok": True}

    @router.get("/auth-events")
    async def auth_events(user=Depends(auth_dep)):
        _owner(user)
        return await db.auth_audit.find({"clinic_id": user["clinic_id"]}, {"_id": 0}).sort("at", -1).to_list(200)

    return router
