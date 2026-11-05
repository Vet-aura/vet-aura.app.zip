"""Staff invitations with role-based access.

Roles per user (stored on the user document):
  - owner       — full access, billing + integrations + team management
  - vet         — DVM: SOAP, differentials, discharges, inbox, receptionist config
  - tech        — Tech: SOAP drafts, inbox, tasks, patients, receptionist config
  - reception   — Front desk: inbox, tasks, receptionist config (no clinical AI signing)

Invitation flow:
  1. Owner (or another owner) POSTs email + role → server creates `invitations` row with a
     random accept-token and a 7-day expiry.
  2. If the clinic has connected an email provider, we send the accept link automatically.
     Otherwise we return the link so the owner can copy/paste (in-app fallback).
  3. New user visits /invite/{token} — if not authenticated, they sign up via /signup?invite=…
     If already authenticated with a different clinic, we refuse and instruct sign out.
  4. On accept, we attach the user to the invited clinic + role and mark the invitation
     accepted. If the accepting user was created via this token, we skip the default
     seed_clinic step.

Signup + auth code lives in /app/backend/auth.py — we integrate through a shim function
`consume_invite` exported here that server.py calls from the signup handler.
"""
from __future__ import annotations
import uuid
import secrets
from datetime import datetime, timezone, timedelta
from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from motor.motor_asyncio import AsyncIOMotorDatabase

from email_service import send_email, EmailNotConfigured

ROLES = ("owner", "vet", "tech", "reception")


class InviteReq(BaseModel):
    email: EmailStr
    role: Literal["owner", "vet", "tech", "reception"] = "vet"
    name: Optional[str] = None


async def consume_invite(db: AsyncIOMotorDatabase, token: str, user_id: str, email: str) -> Optional[dict]:
    """Called from the signup / login handler when a user carries an invite token."""
    inv = await db.invitations.find_one({"token": token, "status": "pending"})
    if not inv:
        return None
    if inv["email"].lower() != email.lower():
        return None
    if inv["expires_at"] < datetime.now(timezone.utc).isoformat():
        await db.invitations.update_one({"_id": inv["_id"]}, {"$set": {"status": "expired"}})
        return None
    # attach to clinic
    await db.users.update_one({"user_id": user_id}, {"$set": {"clinic_id": inv["clinic_id"], "role": inv["role"]}})
    await db.invitations.update_one({"_id": inv["_id"]},
                                    {"$set": {"status": "accepted",
                                              "accepted_at": datetime.now(timezone.utc).isoformat(),
                                              "accepted_by_user_id": user_id}})
    return {"clinic_id": inv["clinic_id"], "role": inv["role"]}


def require_role(*allowed: str):
    def _dep(user=Depends(lambda: None)):
        raise NotImplementedError("Not used directly — wired at server level via auth_dep.")
    return _dep


def build_invitation_routes(db: AsyncIOMotorDatabase, auth_dep, public_app_url_getter):
    router = APIRouter(prefix="/api/team")

    async def _load_clinic(clinic_id: str) -> dict:
        return await db.clinics.find_one({"clinic_id": clinic_id}, {"_id": 0}) or {}

    @router.get("/members")
    async def list_members(user=Depends(auth_dep)):
        cid = user["clinic_id"]
        users = await db.users.find({"clinic_id": cid}, {"_id": 0, "password_hash": 0}).to_list(200)
        return users

    @router.get("/invitations")
    async def list_invitations(user=Depends(auth_dep)):
        cid = user["clinic_id"]
        rows = await db.invitations.find({"clinic_id": cid}, {"_id": 0}).sort("created_at", -1).to_list(200)
        return rows

    @router.post("/invitations")
    async def create_invitation(req: InviteReq, user=Depends(auth_dep)):
        cid = user["clinic_id"]
        if user.get("role", "owner") != "owner":
            raise HTTPException(403, "Only owners can invite team members.")
        # existing user with same email in another clinic?
        existing_user = await db.users.find_one({"email": req.email.lower()})
        if existing_user and existing_user.get("clinic_id") == cid:
            raise HTTPException(400, "This person is already on your team.")
        # duplicate pending invite?
        dup = await db.invitations.find_one({"clinic_id": cid, "email": req.email.lower(), "status": "pending"})
        if dup:
            raise HTTPException(400, "There is already a pending invite for this email.")

        token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        expires_at = (now + timedelta(days=7)).isoformat()
        clinic = await _load_clinic(cid)
        base = public_app_url_getter().rstrip("/")
        invite_url = f"{base}/invite/{token}" if base else f"/invite/{token}"

        doc = {
            "id": str(uuid.uuid4()),
            "clinic_id": cid,
            "email": req.email.lower(),
            "role": req.role,
            "name": req.name or "",
            "token": token,
            "status": "pending",
            "expires_at": expires_at,
            "invited_by": user["email"],
            "created_at": now.isoformat(),
        }
        await db.invitations.insert_one({**doc})
        doc.pop("_id", None)

        # Try to send email; fall back to returning the link.
        delivered = False
        try:
            await send_email(
                db, cid,
                to=req.email,
                subject=f"You've been invited to join {clinic.get('name','Vetaura')}",
                html=f"""<div style='font-family:system-ui,sans-serif;line-height:1.5;color:#0b3a2f'>
                  <h2 style='font-family:Georgia,serif;color:#0b3a2f'>{clinic.get('name','Vetaura')} invited you to Vetaura</h2>
                  <p>Hi {req.name or 'there'},</p>
                  <p>{user['email']} invited you to join <strong>{clinic.get('name','their clinic')}</strong> on Vetaura as a <strong>{req.role}</strong>.</p>
                  <p><a href='{invite_url}' style='display:inline-block;background:#236349;color:#fff;padding:12px 20px;border-radius:999px;text-decoration:none'>Accept invitation</a></p>
                  <p style='color:#4b5563;font-size:12px'>This link expires in 7 days. If you did not expect this, you can ignore this email.</p>
                </div>""",
                text=f"{user['email']} invited you to {clinic.get('name','their clinic')} on Vetaura as a {req.role}. Accept: {invite_url}",
            )
            delivered = True
        except EmailNotConfigured:
            delivered = False
        except Exception:
            delivered = False

        return {**doc, "invite_url": invite_url, "delivered_by_email": delivered}

    @router.delete("/invitations/{invitation_id}")
    async def revoke(invitation_id: str, user=Depends(auth_dep)):
        if user.get("role", "owner") != "owner":
            raise HTTPException(403, "Only owners can revoke invites.")
        r = await db.invitations.delete_one({"id": invitation_id, "clinic_id": user["clinic_id"], "status": "pending"})
        if r.deleted_count == 0:
            raise HTTPException(404, "Invite not found or already accepted.")
        return {"ok": True}

    @router.patch("/members/{user_id}/role")
    async def change_role(user_id: str, req: InviteReq, user=Depends(auth_dep)):
        if user.get("role", "owner") != "owner":
            raise HTTPException(403, "Only owners can change roles.")
        r = await db.users.update_one({"user_id": user_id, "clinic_id": user["clinic_id"]},
                                      {"$set": {"role": req.role}})
        if r.matched_count == 0:
            raise HTTPException(404, "User not found in this clinic.")
        return {"ok": True, "role": req.role}

    @router.delete("/members/{user_id}")
    async def remove_member(user_id: str, user=Depends(auth_dep)):
        if user.get("role", "owner") != "owner":
            raise HTTPException(403, "Only owners can remove members.")
        if user_id == user.get("user_id"):
            raise HTTPException(400, "You cannot remove yourself.")
        r = await db.users.delete_one({"user_id": user_id, "clinic_id": user["clinic_id"]})
        if r.deleted_count == 0:
            raise HTTPException(404, "User not found.")
        return {"ok": True}

    return router


# ---------- Public invite lookup ----------
def build_public_invite_routes(db: AsyncIOMotorDatabase):
    router = APIRouter(prefix="/api/invitations")

    @router.get("/{token}")
    async def peek(token: str):
        inv = await db.invitations.find_one({"token": token}, {"_id": 0})
        if not inv:
            raise HTTPException(404, "Invite not found or already used.")
        if inv["status"] != "pending":
            raise HTTPException(400, f"Invite is {inv['status']}.")
        if inv["expires_at"] < datetime.now(timezone.utc).isoformat():
            raise HTTPException(400, "Invite has expired.")
        clinic = await db.clinics.find_one({"clinic_id": inv["clinic_id"]}, {"_id": 0}) or {}
        return {
            "email": inv["email"],
            "role": inv["role"],
            "name": inv["name"],
            "clinic_name": clinic.get("name"),
            "invited_by": inv["invited_by"],
            "expires_at": inv["expires_at"],
        }

    return router
