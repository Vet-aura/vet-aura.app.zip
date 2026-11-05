"""Combined auth: Emergent Google OAuth + email/password JWT. Multi-tenant clinic scoping."""
import os
import uuid
import bcrypt
import jwt
import httpx
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from motor.motor_asyncio import AsyncIOMotorDatabase
from lead_notify import notify_lead

JWT_SECRET = os.environ.get("JWT_SECRET", "")
if not JWT_SECRET or JWT_SECRET == "change-me" or len(JWT_SECRET) < 32:
    # Fail fast: a missing or weak secret would let anyone forge login tokens.
    raise RuntimeError("JWT_SECRET must be set to a random value of at least 32 characters.")
JWT_ALG = "HS256"
JWT_EXPIRES_DAYS = 7

auth_router = APIRouter(prefix="/api/auth")


# ---------- Models ----------
class SignupReq(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str = Field(min_length=1)
    clinic_name: str | None = None
    invite_token: str | None = None


class LoginReq(BaseModel):
    email: EmailStr
    password: str


class SessionExchangeReq(BaseModel):
    session_id: str
    clinic_name: str | None = None  # provided only on first sign-in


class UserOut(BaseModel):
    user_id: str
    clinic_id: str
    email: str
    name: str
    role: str
    picture: str | None = None
    clinic: dict | None = None


# ---------- Helpers ----------
def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def _verify(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False


def _issue_jwt(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRES_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def _decode_jwt(token: str) -> str | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        return payload.get("sub")
    except Exception:
        return None


async def _seed_clinic(db: AsyncIOMotorDatabase, clinic_id: str):
    """Seed a fresh clinic with demo veterinary data so users can explore immediately."""
    from seed_data import build_seed
    seed = build_seed(clinic_id=clinic_id)
    for coll in ("owners", "patients", "visits", "labs", "weights", "appointments", "messages", "tasks", "care_items"):
        if seed.get(coll):
            await db[coll].insert_many(seed[coll])


async def _create_clinic(db: AsyncIOMotorDatabase, name: str, owner_email: str) -> dict:
    clinic = {
        "clinic_id": f"clinic_{uuid.uuid4().hex[:12]}",
        "name": name,
        "primary_color": "#236349",
        "logo_url": None,
        "discharge_footer": None,
        "plan": "trial",
        "plan_status": "trialing",
        "trial_ends_at": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat(),
        "stripe_customer_id": None,
        "stripe_subscription_id": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "owner_email": owner_email,
        "onboarded": False,
    }
    await db.clinics.insert_one(clinic)
    clinic.pop("_id", None)
    await _seed_clinic(db, clinic["clinic_id"])
    await notify_lead("new clinic signup", {"clinic": name, "email": owner_email})
    return clinic


async def _current_user(request: Request, db: AsyncIOMotorDatabase) -> dict:
    """Extract auth from cookie (session_token) or Authorization header (session_token OR JWT)."""
    token = request.cookies.get("session_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    user_id = None
    # try JWT first
    user_id = _decode_jwt(token)
    if not user_id:
        # try session_token (from Google flow)
        sess = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
        if sess:
            exp = sess.get("expires_at")
            if isinstance(exp, str):
                try:
                    exp = datetime.fromisoformat(exp)
                except Exception:
                    exp = None
            if exp and exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp and exp < datetime.now(timezone.utc):
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired")
            user_id = sess.get("user_id")
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session")

    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


PAST_DUE_GRACE = timedelta(days=7)
BILLING_EXEMPT = ("/api/auth", "/api/payments", "/api/plans", "/api/clinic", "/api/export", "/api/security", "/api/me")


def _parse(ts):
    return datetime.fromisoformat(str(ts).replace("Z", "+00:00")) if ts else None


def clinic_has_access(clinic: dict) -> bool:
    """Active / in-trial / within 7-day past-due grace. Everything else is paywalled."""
    st, now = clinic.get("plan_status"), datetime.now(timezone.utc)
    if st == "active":
        return True
    if st in ("trialing", "trial"):
        end = _parse(clinic.get("trial_ends_at"))
        return bool(clinic.get("stripe_subscription_id")) or (end is not None and end > now)
    if st == "past_due":
        since = _parse(clinic.get("past_due_since"))
        return since is None or now - since < PAST_DUE_GRACE
    return False


def make_auth_dep(db: AsyncIOMotorDatabase):
    async def dep(request: Request) -> dict:
        user = await _current_user(request, db)
        if not request.url.path.startswith(BILLING_EXEMPT):
            clinic = await db.clinics.find_one({"clinic_id": user["clinic_id"]},
                                               {"_id": 0, "plan_status": 1, "trial_ends_at": 1,
                                                "stripe_subscription_id": 1, "past_due_since": 1})
            if clinic and not clinic_has_access(clinic):
                raise HTTPException(402, "Your Vetaura subscription isn't active. Choose a plan in Billing to keep using the app.")
        return user
    return dep


# ---------- Routes ----------
def build_auth_routes(db: AsyncIOMotorDatabase, guard):
    @auth_router.post("/signup")
    async def signup(req: SignupReq, request: Request):
        email = req.email.lower()
        await guard.check(email, request, "signup")
        await guard.record_attempt(email, request, "signup")
        if await db.users.find_one({"email": email}):
            await guard.audit("signup_failed", email, request, reason="email_exists")
            raise HTTPException(400, "Email already registered")

        # Invite flow: attach to existing clinic
        invite = None
        if req.invite_token:
            invite = await db.invitations.find_one({"token": req.invite_token, "status": "pending"})
            if not invite:
                raise HTTPException(400, "Invitation link is invalid or already used.")
            if invite["email"].lower() != req.email.lower():
                raise HTTPException(400, "Invitation email does not match your signup email.")
            if invite["expires_at"] < datetime.now(timezone.utc).isoformat():
                await db.invitations.update_one({"_id": invite["_id"]}, {"$set": {"status": "expired"}})
                raise HTTPException(400, "This invitation has expired.")
            clinic = await db.clinics.find_one({"clinic_id": invite["clinic_id"]}, {"_id": 0})
            if not clinic:
                raise HTTPException(400, "Clinic no longer exists.")
            role = invite["role"]
        else:
            if not (req.clinic_name or "").strip():
                raise HTTPException(400, "Clinic name is required for new sign-ups.")
            clinic = await _create_clinic(db, req.clinic_name, req.email.lower())
            role = "owner"

        user = {
            "user_id": f"user_{uuid.uuid4().hex[:12]}",
            "clinic_id": clinic["clinic_id"],
            "email": req.email.lower(),
            "name": req.name,
            "role": role,
            "picture": None,
            "password_hash": _hash(req.password),
            "auth_method": "password",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.users.insert_one(user)
        user.pop("_id", None)

        if invite:
            await db.invitations.update_one(
                {"_id": invite["_id"]},
                {"$set": {"status": "accepted",
                          "accepted_at": datetime.now(timezone.utc).isoformat(),
                          "accepted_by_user_id": user["user_id"]}},
            )

        await guard.audit("signup_success", email, request, user)
        token = _issue_jwt(user["user_id"])
        return {"token": token, "user": {**{k: user[k] for k in ("user_id", "clinic_id", "email", "name", "role", "picture")}, "clinic": clinic}}

    @auth_router.post("/login")
    async def login(req: LoginReq, request: Request):
        email = req.email.lower()
        await guard.check(email, request, "login")
        user = await db.users.find_one({"email": email}, {"_id": 0})
        if not user or not user.get("password_hash") or not _verify(req.password, user["password_hash"]):
            await guard.record_login_failure(email, request, user)
            raise HTTPException(401, "Invalid credentials")
        await guard.record_login_success(email, request, user)
        clinic = await db.clinics.find_one({"clinic_id": user["clinic_id"]}, {"_id": 0})
        token = _issue_jwt(user["user_id"])
        return {"token": token, "user": {**{k: user.get(k) for k in ("user_id", "clinic_id", "email", "name", "role", "picture")}, "clinic": clinic}}

    @auth_router.post("/session")
    async def google_session(req: SessionExchangeReq, response: Response):
        """Exchange Emergent Google session_id for our session_token."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(
                    "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
                    headers={"X-Session-ID": req.session_id},
                )
                r.raise_for_status()
                data = r.json()
        except Exception:
            raise HTTPException(401, "Invalid session_id")

        email = (data.get("email") or "").lower()
        name = data.get("name") or email.split("@")[0]
        picture = data.get("picture")
        session_token = data.get("session_token")
        if not email or not session_token:
            raise HTTPException(401, "Incomplete session data")

        user = await db.users.find_one({"email": email}, {"_id": 0})
        if not user:
            # Create clinic + user
            clinic_name = req.clinic_name or f"{name}'s Clinic"
            clinic = await _create_clinic(db, clinic_name, email)
            user = {
                "user_id": f"user_{uuid.uuid4().hex[:12]}",
                "clinic_id": clinic["clinic_id"],
                "email": email,
                "name": name,
                "role": "owner",
                "picture": picture,
                "auth_method": "google",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.users.insert_one(user)
            user.pop("_id", None)
        else:
            # Update picture on re-sign-in
            await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"picture": picture, "name": name}})
            clinic = await db.clinics.find_one({"clinic_id": user["clinic_id"]}, {"_id": 0})

        # Store session_token
        await db.user_sessions.insert_one({
            "user_id": user["user_id"],
            "session_token": session_token,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        # Also set httpOnly cookie
        response.set_cookie(
            "session_token", session_token,
            httponly=True, secure=True, samesite="none",
            path="/", max_age=7 * 24 * 60 * 60,
        )
        return {"token": session_token, "user": {**{k: user.get(k) for k in ("user_id", "clinic_id", "email", "name", "role", "picture")}, "clinic": clinic}}

    @auth_router.get("/me")
    async def me(request: Request):
        user = await _current_user(request, db)
        clinic = await db.clinics.find_one({"clinic_id": user["clinic_id"]}, {"_id": 0}) or {}
        clinic["billing_access"] = clinic_has_access(clinic)
        return {"user_id": user["user_id"], "clinic_id": user["clinic_id"], "email": user["email"], "name": user["name"], "role": user.get("role", "owner"), "picture": user.get("picture"), "clinic": clinic}

    @auth_router.post("/logout")
    async def logout(request: Request, response: Response):
        token = request.cookies.get("session_token") or (request.headers.get("Authorization", "").replace("Bearer ", "").strip() or None)
        if token:
            await db.user_sessions.delete_one({"session_token": token})
        response.delete_cookie("session_token", path="/")
        return {"ok": True}

    return auth_router
