"""Staff 'My mobile number' with one-time SMS code verification (used for blast test sends)."""
import hashlib
import hmac
import secrets
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorDatabase
from sms_compliance import _normalize_phone
from sms_sender import send_raw_sms

CODE_TTL = timedelta(minutes=10)
MAX_STARTS_PER_HOUR = 5
MAX_VERIFY_ATTEMPTS = 5


def code_hash(user_id: str, code: str) -> str:
    return hashlib.sha256(f"{user_id}:{code}".encode()).hexdigest()


class StartReq(BaseModel):
    phone: str = Field(min_length=7, max_length=25)


class VerifyReq(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


def build_phone_verify_routes(db: AsyncIOMotorDatabase, auth_dep):
    router = APIRouter(prefix="/api/me/mobile")

    @router.get("")
    async def get_mobile(user=Depends(auth_dep)):
        u = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "mobile_phone": 1, "mobile_verified": 1})
        return {"phone": (u or {}).get("mobile_phone"), "verified": bool((u or {}).get("mobile_verified"))}

    @router.post("/start")
    async def start(req: StartReq, user=Depends(auth_dep)):
        phone = _normalize_phone(req.phone)
        if not phone.startswith("+") or len(phone) < 11:
            raise HTTPException(400, "Enter a full mobile number, e.g. (415) 555-0142 or +14155550142.")
        now = datetime.now(timezone.utc)
        recent = await db.phone_verify_attempts.count_documents(
            {"user_id": user["user_id"], "at": {"$gte": (now - timedelta(hours=1)).isoformat()}})
        if recent >= MAX_STARTS_PER_HOUR:
            raise HTTPException(429, "Too many codes requested. Try again in an hour.")
        await db.phone_verify_attempts.insert_one({"user_id": user["user_id"], "phone": phone, "at": now.isoformat()})
        code = f"{secrets.randbelow(10**6):06d}"
        doc = {"user_id": user["user_id"], "clinic_id": user["clinic_id"], "phone": phone,
               "code_hash": code_hash(user["user_id"], code), "attempts": 0, "used": False,
               "created_at": now.isoformat(), "expires_at": (now + CODE_TTL).isoformat()}
        res = await db.phone_verifications.insert_one(doc)
        try:
            await send_raw_sms(db, user["clinic_id"], phone,
                               f"Your Vetaura verification code is {code}. It expires in 10 minutes.", "otp")
        except Exception as e:
            await db.phone_verifications.delete_one({"_id": res.inserted_id})
            raise HTTPException(400, f"Couldn't send the code through your clinic's Twilio number: {str(e)[:160]}")
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"mobile_phone": phone, "mobile_verified": False}})
        return {"ok": True, "phone": phone}

    @router.post("/verify")
    async def verify(req: VerifyReq, user=Depends(auth_dep)):
        now = datetime.now(timezone.utc).isoformat()
        v = await db.phone_verifications.find_one(
            {"user_id": user["user_id"], "used": False, "expires_at": {"$gt": now}}, sort=[("created_at", -1)])
        if not v or v["attempts"] >= MAX_VERIFY_ATTEMPTS:
            raise HTTPException(400, "Code expired or too many attempts. Request a new code.")
        if not hmac.compare_digest(v["code_hash"], code_hash(user["user_id"], req.code)):
            await db.phone_verifications.update_one({"_id": v["_id"]}, {"$inc": {"attempts": 1}})
            raise HTTPException(400, "That code doesn't match.")
        await db.phone_verifications.update_one({"_id": v["_id"]}, {"$set": {"used": True}})
        await db.users.update_one({"user_id": user["user_id"]},
                                  {"$set": {"mobile_phone": v["phone"], "mobile_verified": True, "mobile_verified_at": now}})
        return {"phone": v["phone"], "verified": True}

    @router.delete("")
    async def remove(user=Depends(auth_dep)):
        await db.users.update_one({"user_id": user["user_id"]}, {"$unset": {"mobile_phone": "", "mobile_verified": ""}})
        return {"ok": True}

    return router
