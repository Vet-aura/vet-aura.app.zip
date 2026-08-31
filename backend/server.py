"""Vetaura backend — FastAPI + MongoDB + Claude Sonnet 5 + Whisper + Auth + Stripe."""
from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Depends, Request
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os, logging, uuid, io, csv
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime, timezone, timedelta

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from ai_service import (
    transcribe_audio, generate_soap, generate_differentials,
    generate_discharge, draft_reply, generate_handoff,
    receptionist_reply,
)
from seed_data import build_seed
from auth import build_auth_routes, make_auth_dep
from stripe_service import ensure_catalog, build_stripe_routes, get_tax_mode

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("vetaura")

mongo_url = os.environ["MONGO_URL"]
mongo = AsyncIOMotorClient(mongo_url)
db = mongo[os.environ["DB_NAME"]]

app = FastAPI(title="Vetaura API")

# Auth dependency (scoped to db)
auth_dep = make_auth_dep(db)

api = APIRouter(prefix="/api")


# ---------- Startup ----------
@app.on_event("startup")
async def startup():
    # Ensure demo clinic exists (single-tenant fallback for public browsing)
    if await db.patients.count_documents({"clinic_id": "demo"}) == 0:
        seed = build_seed(clinic_id="demo")
        for coll in ("owners", "patients", "visits", "labs", "weights", "appointments", "messages", "tasks"):
            if seed.get(coll):
                await db[coll].insert_many(seed[coll])
        # Backfill legacy docs (missing clinic_id) to demo
        for coll in ("owners", "patients", "visits", "labs", "weights", "appointments", "messages", "soap_notes"):
            await db[coll].update_many({"clinic_id": {"$exists": False}}, {"$set": {"clinic_id": "demo"}})
        logger.info("Vetaura demo clinic seeded.")
    # Ensure Stripe products/prices exist
    try:
        ensure_catalog()
    except Exception as e:
        logger.warning(f"Stripe ensure_catalog failed: {e}")


@app.on_event("shutdown")
async def shutdown():
    mongo.close()


def clean(doc):
    if not doc:
        return doc
    doc.pop("_id", None)
    return doc


# ---------- Audit helper ----------
async def audit(user, action: str, target: str = "", metadata: dict | None = None):
    await db.audit_log.insert_one({
        "id": str(uuid.uuid4()),
        "clinic_id": user["clinic_id"],
        "user_id": user["user_id"],
        "user_name": user.get("name"),
        "action": action,
        "target": target,
        "metadata": metadata or {},
        "at": datetime.now(timezone.utc).isoformat(),
    })


# ---------- Models ----------
class SoapReq(BaseModel):
    transcript: str
    patient_id: Optional[str] = None


class DifferentialReq(BaseModel):
    signalment: str
    complaint: str
    findings: str


class DischargeReq(BaseModel):
    pet_name: str
    plan_notes: str
    language: str = "English"
    patient_id: Optional[str] = None
    share: bool = False  # create public link


class ReplyReq(BaseModel):
    client_message: str
    patient_context: Optional[str] = ""


class HandoffReq(BaseModel):
    cases_summary: Optional[str] = None


class SoapSaveReq(BaseModel):
    patient_id: str
    appointment_id: Optional[str] = None
    subjective: str
    objective: str
    assessment: str
    plan: str


class ClinicUpdateReq(BaseModel):
    name: Optional[str] = None
    primary_color: Optional[str] = None
    logo_url: Optional[str] = None
    discharge_footer: Optional[str] = None
    onboarded: Optional[bool] = None


class DemoReq(BaseModel):
    name: str
    email: EmailStr
    clinic: str
    message: Optional[str] = ""


class TaskCreateReq(BaseModel):
    patient_id: Optional[str] = None
    title: str
    description: Optional[str] = ""
    due_date: Optional[str] = None
    priority: str = "normal"  # low|normal|high|urgent
    source: str = "manual"
    source_id: Optional[str] = None


class TaskPatchReq(BaseModel):
    status: Optional[str] = None  # open|completed|dismissed
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[str] = None
    priority: Optional[str] = None


class MessageStatusReq(BaseModel):
    status: str  # new|drafted|sent|awaiting_reply|booked|paid|closed


class ReceptionistConfigReq(BaseModel):
    enabled: Optional[bool] = None
    hours_text: Optional[str] = None
    address: Optional[str] = None
    emergency_phone: Optional[str] = None
    emergency_instructions: Optional[str] = None
    species: Optional[list[str]] = None
    appt_types: Optional[list[str]] = None
    pricing_text: Optional[str] = None
    vaccine_requirements: Optional[str] = None
    medication_policy: Optional[str] = None
    new_client_policy: Optional[str] = None
    deposit_policy: Optional[str] = None
    faqs: Optional[list[dict]] = None  # [{q,a}]
    greeting: Optional[str] = None


class ReceptionistChatReq(BaseModel):
    clinic_id: str
    session_id: str
    message: str


class ReceptionistBookReq(BaseModel):
    clinic_id: str
    session_id: str
    pet_name: str
    species: str
    breed: Optional[str] = ""
    age: Optional[str] = ""
    reason: str
    owner_name: str
    owner_phone: str
    preferred_time: Optional[str] = ""


# ---------- Emergency keyword safety net ----------
EMERGENCY_KEYWORDS = [
    "collapse", "collapsed", "seizure", "seizing", "unresponsive", "not breathing",
    "difficulty breathing", "dyspnea", "gasping", "hit by car", "hit-by-car", "hbc",
    "bloat", "bloated", "distended", "toxin", "poison", "chocolate", "grape", "xylitol",
    "uncontrolled bleeding", "bleeding heavily", "won't stop bleeding", "hemorrhage",
    "unable to urinate", "blocked cat",
]

def emergency_keyword_hit(text: str) -> str | None:
    t = (text or "").lower()
    for kw in EMERGENCY_KEYWORDS:
        if kw in t:
            return kw
    return None


async def create_task(db, clinic_id: str, patient_id: str | None, title: str, description: str = "", priority: str = "normal", source: str = "auto", source_id: str | None = None, due_days: int = 0):
    doc = {
        "id": str(uuid.uuid4()),
        "clinic_id": clinic_id,
        "patient_id": patient_id,
        "title": title,
        "description": description,
        "priority": priority,
        "status": "open",
        "source": source,
        "source_id": source_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "due_date": (datetime.now(timezone.utc) + timedelta(days=due_days)).isoformat() if due_days else datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
    }
    await db.tasks.insert_one(doc)
    doc.pop("_id", None)
    return doc


# ---------- Public / basic ----------
@api.get("/")
async def root():
    return {"service": "Vetaura", "status": "ok", "tax_mode": get_tax_mode()}


@api.post("/marketing/demo")
async def marketing_demo(req: DemoReq):
    await db.demo_requests.insert_one({
        "id": str(uuid.uuid4()),
        **req.model_dump(),
        "at": datetime.now(timezone.utc).isoformat(),
    })
    return {"ok": True}


# ---------- Stats & core data (auth-gated) ----------
@api.get("/stats")
async def stats(user=Depends(auth_dep)):
    cid = user["clinic_id"]
    return {
        "patients": await db.patients.count_documents({"clinic_id": cid}),
        "appointments_today": await db.appointments.count_documents({"clinic_id": cid}),
        "open_messages": await db.messages.count_documents({"clinic_id": cid, "status": {"$in": ["new", "drafted", "awaiting_reply"]}}),
        "open_tasks": await db.tasks.count_documents({"clinic_id": cid, "status": "open"}),
        "urgent_tasks": await db.tasks.count_documents({"clinic_id": cid, "status": "open", "priority": "urgent"}),
        "signed_notes": await db.soap_notes.count_documents({"clinic_id": cid, "signed_by": {"$ne": None}}),
        "draft_notes": await db.soap_notes.count_documents({"clinic_id": cid, "signed_by": None}),
    }


@api.get("/owners")
async def list_owners(user=Depends(auth_dep)):
    return [clean(o) for o in await db.owners.find({"clinic_id": user["clinic_id"]}).to_list(500)]


@api.get("/patients")
async def list_patients(user=Depends(auth_dep)):
    cid = user["clinic_id"]
    patients = [clean(p) for p in await db.patients.find({"clinic_id": cid}).to_list(500)]
    owners = {o["id"]: o for o in [clean(x) for x in await db.owners.find({"clinic_id": cid}).to_list(500)]}
    for p in patients:
        p["owner"] = owners.get(p.get("owner_id"))
    return patients


@api.get("/patients/{pid}")
async def get_patient(pid: str, user=Depends(auth_dep)):
    cid = user["clinic_id"]
    p = clean(await db.patients.find_one({"id": pid, "clinic_id": cid}))
    if not p:
        raise HTTPException(404, "Patient not found")
    p["owner"] = clean(await db.owners.find_one({"id": p.get("owner_id"), "clinic_id": cid}))
    p["visits"] = [clean(v) for v in await db.visits.find({"patient_id": pid, "clinic_id": cid}).sort("date", -1).to_list(200)]
    p["labs"] = sorted([clean(l) for l in await db.labs.find({"patient_id": pid, "clinic_id": cid}).to_list(200)], key=lambda x: x["date"])
    p["weights"] = sorted([clean(w) for w in await db.weights.find({"patient_id": pid, "clinic_id": cid}).to_list(200)], key=lambda x: x["date"])
    p["soap_notes"] = [clean(s) for s in await db.soap_notes.find({"patient_id": pid, "clinic_id": cid}).sort("created_at", -1).to_list(200)]
    return p


@api.get("/appointments")
async def list_appointments(user=Depends(auth_dep)):
    cid = user["clinic_id"]
    apts = [clean(a) for a in await db.appointments.find({"clinic_id": cid}).sort("datetime", 1).to_list(200)]
    pats = {p["id"]: p for p in [clean(x) for x in await db.patients.find({"clinic_id": cid}).to_list(500)]}
    owners = {o["id"]: o for o in [clean(x) for x in await db.owners.find({"clinic_id": cid}).to_list(500)]}
    for a in apts:
        pat = pats.get(a.get("patient_id"), {})
        a["patient"] = pat
        a["owner"] = owners.get(pat.get("owner_id"))
    return apts


@api.get("/messages")
async def list_messages(user=Depends(auth_dep)):
    cid = user["clinic_id"]
    msgs = [clean(m) for m in await db.messages.find({"clinic_id": cid}).sort("received_at", -1).to_list(200)]
    pats = {p["id"]: p for p in [clean(x) for x in await db.patients.find({"clinic_id": cid}).to_list(500)]}
    owners = {o["id"]: o for o in [clean(x) for x in await db.owners.find({"clinic_id": cid}).to_list(500)]}
    for m in msgs:
        m["patient"] = pats.get(m.get("patient_id"))
        m["owner"] = owners.get(m.get("owner_id"))
    return msgs


@api.post("/messages/{mid}/draft")
async def message_draft(mid: str, user=Depends(auth_dep)):
    cid = user["clinic_id"]
    m = await db.messages.find_one({"id": mid, "clinic_id": cid})
    if not m:
        raise HTTPException(404, "Message not found")
    pat = await db.patients.find_one({"id": m.get("patient_id"), "clinic_id": cid}) or {}
    context = f"Pet: {pat.get('name')} — {pat.get('species')} — {pat.get('breed')}, age {pat.get('age_years')}. Active problems: {', '.join(pat.get('active_problems', []))}."
    draft = await draft_reply(m["body"], context)

    # Deterministic emergency-keyword safety net (belt & suspenders on top of Claude)
    kw = emergency_keyword_hit(m["body"])
    if kw:
        draft["category"] = "urgent_review"
        draft["urgency"] = "urgent"
        prior_note = draft.get("internal_note") or ""
        draft["internal_note"] = f"[EMERGENCY KEYWORD DETECTED: '{kw}'] {prior_note}".strip()

    await db.messages.update_one({"id": mid, "clinic_id": cid}, {"$set": {
        "draft": draft,
        "category": draft.get("category", "routine"),
        "status": "drafted",
    }})

    # Auto-create task if urgent OR the AI suggests one
    if draft.get("category") == "urgent_review":
        await create_task(
            db, cid, m.get("patient_id"),
            title=f"URGENT REVIEW — call {pat.get('name') or 'owner'} now",
            description=(m["body"][:220] + "…") if len(m["body"]) > 220 else m["body"],
            priority="urgent", source="message", source_id=mid,
        )
    elif draft.get("suggests_task"):
        await create_task(
            db, cid, m.get("patient_id"),
            title=draft["suggests_task"],
            description=draft.get("one_line_summary", ""),
            priority="high" if draft.get("category") in ("appointment_needed", "refill_request", "lab_follow_up") else "normal",
            source="message", source_id=mid, due_days=1,
        )

    await audit(user, "ai_draft_reply", target=mid, metadata={"category": draft.get("category")})
    return draft


@api.patch("/messages/{mid}/status")
async def message_status(mid: str, req: MessageStatusReq, user=Depends(auth_dep)):
    if req.status not in {"new", "drafted", "sent", "awaiting_reply", "booked", "paid", "closed"}:
        raise HTTPException(400, "Invalid status")
    r = await db.messages.update_one(
        {"id": mid, "clinic_id": user["clinic_id"]},
        {"$set": {"status": req.status, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    if r.matched_count == 0:
        raise HTTPException(404, "Message not found")
    await audit(user, "message_status", target=mid, metadata={"status": req.status})
    return {"ok": True, "status": req.status}


@api.post("/messages/{mid}/approve")
async def message_approve(mid: str, user=Depends(auth_dep)):
    m = await db.messages.find_one({"id": mid, "clinic_id": user["clinic_id"]})
    if not m:
        raise HTTPException(404, "Message not found")
    await db.messages.update_one({"id": mid, "clinic_id": user["clinic_id"]}, {"$set": {"status": "sent"}})

    # Auto-create follow-up task per category on approve
    cat = m.get("category")
    if cat == "refill_request":
        await create_task(db, user["clinic_id"], m.get("patient_id"),
            title="Refill: verify Rx & prep pickup",
            description=f"Approved refill reply for message #{mid}",
            priority="normal", source="message", source_id=mid, due_days=0)
    elif cat == "appointment_needed":
        await create_task(db, user["clinic_id"], m.get("patient_id"),
            title="Book appointment — owner confirmed",
            description=f"Owner replied to appointment offer for message #{mid}",
            priority="high", source="message", source_id=mid, due_days=1)
    elif cat == "lab_follow_up":
        await create_task(db, user["clinic_id"], m.get("patient_id"),
            title="Lab follow-up: confirm plan understood",
            description=f"Follow up on lab explanation from message #{mid}",
            priority="normal", source="message", source_id=mid, due_days=3)

    await audit(user, "message_approved", target=mid)
    return {"ok": True}


# ---------- Ambient Scribe ----------
@api.post("/scribe/transcribe")
async def scribe_transcribe(audio: UploadFile = File(...), user=Depends(auth_dep)):
    data = await audio.read()
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(413, "Audio must be under 25 MB")
    text = await transcribe_audio(data, filename=audio.filename or "audio.webm")
    await audit(user, "whisper_transcribe", metadata={"bytes": len(data)})
    return {"transcript": text}


@api.post("/scribe/soap")
async def scribe_soap(req: SoapReq, user=Depends(auth_dep)):
    context = ""
    if req.patient_id:
        pat = await db.patients.find_one({"id": req.patient_id, "clinic_id": user["clinic_id"]})
        if pat:
            context = f"Pet: {pat['name']} — {pat['species']} — {pat['breed']}, age {pat['age_years']}, {pat.get('sex','')}, {pat.get('weight_kg','?')}kg. Active problems: {', '.join(pat.get('active_problems', []))}."
    result = await generate_soap(req.transcript, context)
    await audit(user, "ai_soap_draft", target=req.patient_id or "")
    return result


@api.post("/scribe/save")
async def scribe_save(req: SoapSaveReq, user=Depends(auth_dep)):
    doc = {
        "id": str(uuid.uuid4()),
        "clinic_id": user["clinic_id"],
        "patient_id": req.patient_id,
        "appointment_id": req.appointment_id,
        "subjective": req.subjective,
        "objective": req.objective,
        "assessment": req.assessment,
        "plan": req.plan,
        "signed_by": user["name"],
        "signed_by_id": user["user_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.soap_notes.insert_one(doc)
    doc.pop("_id", None)
    await audit(user, "soap_signed", target=req.patient_id, metadata={"note_id": doc["id"]})
    return doc


@api.post("/ai/differentials")
async def ai_diffs(req: DifferentialReq, user=Depends(auth_dep)):
    result = await generate_differentials(req.signalment, req.complaint, req.findings)
    await audit(user, "ai_differentials")
    return result


@api.post("/ai/discharge")
async def ai_discharge(req: DischargeReq, user=Depends(auth_dep)):
    result = await generate_discharge(req.pet_name, req.plan_notes, req.language)
    await audit(user, "ai_discharge", metadata={"language": req.language})
    if req.share:
        token = uuid.uuid4().hex
        clinic = await db.clinics.find_one({"clinic_id": user["clinic_id"]}, {"_id": 0})
        share_doc = {
            "id": str(uuid.uuid4()),
            "token": token,
            "clinic_id": user["clinic_id"],
            "clinic_name": (clinic or {}).get("name") or "Your veterinary clinic",
            "clinic_logo": (clinic or {}).get("logo_url"),
            "primary_color": (clinic or {}).get("primary_color") or "#236349",
            "footer": (clinic or {}).get("discharge_footer"),
            "pet_name": req.pet_name,
            "patient_id": req.patient_id,
            "language": req.language,
            "content": result,
            "signed_by": user["name"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.discharge_shares.insert_one(share_doc)
        result = {**result, "share_token": token}
        await audit(user, "discharge_shared", metadata={"token": token, "pet": req.pet_name})
    return result


@api.get("/discharge/public/{token}")
async def discharge_public(token: str):
    doc = await db.discharge_shares.find_one({"token": token}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Not found")
    return doc


@api.post("/ai/handoff")
async def ai_handoff(req: HandoffReq, user=Depends(auth_dep)):
    if req.cases_summary:
        summary = req.cases_summary
    else:
        pats = [clean(p) for p in await db.patients.find({"clinic_id": user["clinic_id"]}).to_list(200)]
        lines = []
        for p in pats:
            lines.append(f"- {p['name']} ({p['species']}, {p['breed']}, {p['age_years']}y): problems={p.get('active_problems', [])}; alerts={p.get('alerts', [])}")
        summary = "\n".join(lines)
    result = await generate_handoff(summary)
    await audit(user, "ai_handoff")
    return result


# ---------- Tasks / Follow-ups ----------
@api.get("/tasks")
async def list_tasks(user=Depends(auth_dep), status: Optional[str] = None):
    q = {"clinic_id": user["clinic_id"]}
    if status:
        q["status"] = status
    tasks = [clean(t) for t in await db.tasks.find(q).sort("due_date", 1).to_list(500)]
    pats = {p["id"]: p for p in [clean(x) for x in await db.patients.find({"clinic_id": user["clinic_id"]}).to_list(500)]}
    for t in tasks:
        t["patient"] = pats.get(t.get("patient_id"))
    return tasks


@api.post("/tasks")
async def create_manual_task(req: TaskCreateReq, user=Depends(auth_dep)):
    doc = {
        "id": str(uuid.uuid4()),
        "clinic_id": user["clinic_id"],
        "patient_id": req.patient_id,
        "title": req.title,
        "description": req.description,
        "priority": req.priority,
        "status": "open",
        "source": req.source,
        "source_id": req.source_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "due_date": req.due_date or datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
    }
    await db.tasks.insert_one(doc)
    doc.pop("_id", None)
    await audit(user, "task_created", target=doc["id"], metadata={"title": req.title})
    return doc


@api.patch("/tasks/{tid}")
async def patch_task(tid: str, req: TaskPatchReq, user=Depends(auth_dep)):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No changes")
    if updates.get("status") == "completed":
        updates["completed_at"] = datetime.now(timezone.utc).isoformat()
    r = await db.tasks.update_one({"id": tid, "clinic_id": user["clinic_id"]}, {"$set": updates})
    if r.matched_count == 0:
        raise HTTPException(404, "Task not found")
    await audit(user, "task_updated", target=tid, metadata=updates)
    return await db.tasks.find_one({"id": tid, "clinic_id": user["clinic_id"]}, {"_id": 0})


@api.post("/tasks/auto-generate")
async def auto_generate_tasks(user=Depends(auth_dep)):
    """Scan clinic data and create auto-tasks for known follow-up scenarios."""
    cid = user["clinic_id"]
    created = 0
    now = datetime.now(timezone.utc)

    # Only create tasks that don't already exist for the same source_id
    async def maybe_create(patient_id, title, description, priority, source, source_id, due_days=0):
        nonlocal created
        exists = await db.tasks.find_one({"clinic_id": cid, "source_id": source_id, "title": title})
        if exists:
            return
        await create_task(db, cid, patient_id, title, description, priority, source, source_id, due_days)
        created += 1

    patients = [clean(p) for p in await db.patients.find({"clinic_id": cid}).to_list(500)]

    # Trigger 1: Post-op patients — schedule day 3/7/10 rechecks (if not already signaled)
    for p in patients:
        for prob in (p.get("active_problems") or []):
            pl = prob.lower()
            if "post-op" in pl or "post op" in pl or "tplo" in pl or "spay" in pl or "neuter" in pl:
                await maybe_create(p["id"],
                    title=f"Post-op check-in call — {p['name']}",
                    description=f"Call owner to verify recovery: incision, appetite, activity restriction ({prob}).",
                    priority="high", source="auto_postop", source_id=f"postop_{p['id']}", due_days=1)

        # Trigger 2: Chronic condition monitoring (CKD / diabetes / atopy / seizures)
        for prob in (p.get("active_problems") or []):
            pl = prob.lower()
            if any(k in pl for k in ["kidney", "ckd", "diabetes", "atopic", "seizure", "cushing", "hyperthyroid", "cardiac", "arthritis"]):
                await maybe_create(p["id"],
                    title=f"Monitoring due — {p['name']} ({prob})",
                    description="Chronic condition monitoring window is open. Book bloodwork or recheck.",
                    priority="normal", source="auto_chronic", source_id=f"chronic_{p['id']}_{prob[:12]}", due_days=7)

        # Trigger 3: Alerts (overdue vaccines etc.)
        for alert in (p.get("alerts") or []):
            await maybe_create(p["id"],
                title=f"Care gap — {p['name']}",
                description=alert,
                priority="normal", source="auto_alert", source_id=f"alert_{p['id']}_{alert[:12]}", due_days=3)

    # Trigger 4: Unreplied messages older than 4 hours (demo threshold)
    stale_cutoff = (now - timedelta(hours=4)).isoformat()
    stale = await db.messages.find({"clinic_id": cid, "status": {"$in": ["new"]}, "received_at": {"$lte": stale_cutoff}}).to_list(200)
    for m in stale:
        await maybe_create(m.get("patient_id"),
            title=f"Stale message — reply to {m.get('subject')}",
            description=(m.get("body") or "")[:200],
            priority="high", source="auto_stale_msg", source_id=f"msg_{m['id']}")

    await audit(user, "tasks_auto_generated", metadata={"count": created})
    return {"created": created}


# ---------- Care & Revenue Gaps ----------
@api.get("/care-gaps")
async def care_gaps(user=Depends(auth_dep)):
    cid = user["clinic_id"]
    patients = [clean(p) for p in await db.patients.find({"clinic_id": cid}).to_list(500)]
    owners = {o["id"]: o for o in [clean(x) for x in await db.owners.find({"clinic_id": cid}).to_list(500)]}
    visits_by_patient = {}
    for v in await db.visits.find({"clinic_id": cid}).to_list(1000):
        visits_by_patient.setdefault(v["patient_id"], []).append(clean(v))

    gaps = []
    now = datetime.now(timezone.utc)
    for p in patients:
        rows = []

        # Explicit alerts
        for alert in (p.get("alerts") or []):
            rows.append({"kind": "alert", "label": alert, "severity": "high"})

        # Chronic monitoring signal
        for prob in (p.get("active_problems") or []):
            pl = prob.lower()
            if any(k in pl for k in ["kidney", "ckd", "diabetes"]):
                rows.append({"kind": "monitoring", "label": f"Monitoring bloodwork for {prob}", "severity": "high"})
            elif any(k in pl for k in ["atopic", "otitis"]):
                rows.append({"kind": "monitoring", "label": f"Recheck for {prob}", "severity": "normal"})

        # Dental gap heuristic (no dental visit in > 12 months for dogs/cats age >= 3)
        pv = visits_by_patient.get(p["id"], [])
        last_dental = None
        for v in pv:
            t = (v.get("type") or "").lower()
            r = (v.get("reason") or "").lower()
            if "dental" in t or "dental" in r:
                dt = v.get("date")
                if dt and (not last_dental or dt > last_dental):
                    last_dental = dt
        if p.get("age_years", 0) >= 3 and (not last_dental or (now - datetime.fromisoformat(last_dental.replace("Z", "+00:00"))).days > 365):
            rows.append({"kind": "dental", "label": "Dental exam overdue (>12 months)", "severity": "normal"})

        # Heartworm test heuristic — dogs need annual HWT
        if p.get("species", "").lower() == "canine":
            rows.append({"kind": "hwt", "label": "Annual heartworm test due", "severity": "normal"})

        if rows:
            gaps.append({
                "patient": p,
                "owner": owners.get(p.get("owner_id")),
                "gaps": rows,
            })
    return gaps


# ---------- Clinic settings ----------
@api.get("/clinic")
async def get_clinic(user=Depends(auth_dep)):
    return await db.clinics.find_one({"clinic_id": user["clinic_id"]}, {"_id": 0})


@api.patch("/clinic")
async def update_clinic(req: ClinicUpdateReq, user=Depends(auth_dep)):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No changes")
    await db.clinics.update_one({"clinic_id": user["clinic_id"]}, {"$set": updates})
    await audit(user, "clinic_updated", metadata=updates)
    return await db.clinics.find_one({"clinic_id": user["clinic_id"]}, {"_id": 0})


# ---------- Audit log ----------
@api.get("/audit")
async def audit_list(user=Depends(auth_dep)):
    items = [clean(a) for a in await db.audit_log.find({"clinic_id": user["clinic_id"]}).sort("at", -1).to_list(500)]
    return items


# ---------- CSV exports ----------
@api.get("/export/patients.csv")
async def export_patients_csv(user=Depends(auth_dep)):
    cid = user["clinic_id"]
    patients = [clean(p) for p in await db.patients.find({"clinic_id": cid}).to_list(1000)]
    owners = {o["id"]: o for o in [clean(x) for x in await db.owners.find({"clinic_id": cid}).to_list(1000)]}
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Name", "Species", "Breed", "Age", "Sex", "Weight (kg)", "Microchip", "Owner", "Owner email", "Owner phone", "Active problems", "Alerts"])
    for p in patients:
        o = owners.get(p.get("owner_id"), {})
        w.writerow([p.get("name"), p.get("species"), p.get("breed"), p.get("age_years"), p.get("sex"), p.get("weight_kg"), p.get("microchip"), o.get("name"), o.get("email"), o.get("phone"), "; ".join(p.get("active_problems", [])), "; ".join(p.get("alerts", []))])
    await audit(user, "export_patients_csv")
    return PlainTextResponse(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=vetaura_patients.csv"})


@api.get("/export/notes.csv")
async def export_notes_csv(user=Depends(auth_dep)):
    cid = user["clinic_id"]
    notes = [clean(n) for n in await db.soap_notes.find({"clinic_id": cid}).sort("created_at", -1).to_list(1000)]
    pats = {p["id"]: p for p in [clean(x) for x in await db.patients.find({"clinic_id": cid}).to_list(1000)]}
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Date", "Patient", "Signed by", "Subjective", "Objective", "Assessment", "Plan"])
    for n in notes:
        p = pats.get(n.get("patient_id"), {})
        w.writerow([n.get("created_at"), p.get("name"), n.get("signed_by"), n.get("subjective"), n.get("objective"), n.get("assessment"), n.get("plan")])
    await audit(user, "export_notes_csv")
    return PlainTextResponse(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=vetaura_notes.csv"})


# ---------- AI Vet Receptionist ----------
DEFAULT_RECEPTIONIST = {
    "enabled": True,
    "hours_text": "Mon–Fri 8:00am–6:00pm · Sat 9:00am–2:00pm · Closed Sun",
    "address": "1200 Meadow Ridge Ln, Suite 4",
    "emergency_phone": "(415) 555-0100 ext 2",
    "emergency_instructions": "This may be a medical emergency. Please head to the nearest emergency veterinary hospital immediately, or call our emergency line at (415) 555-0100 ext 2.",
    "species": ["Canine", "Feline"],
    "appt_types": ["Wellness exam", "Sick visit", "Vaccine only", "Dental consult", "Surgical consult", "Recheck", "Nail trim"],
    "pricing_text": "Wellness exam $75–$120 · Vaccines $35–$65 each · Dental cleaning $450–$900 · Bloodwork panel $110–$220. Final cost depends on findings and any medications prescribed by the veterinarian.",
    "vaccine_requirements": "Dogs: Rabies (annual or 3-year), DA2PP (annual or 3-year), Bordetella (annual). Cats: Rabies (annual or 3-year), FVRCP (annual or 3-year), FeLV for outdoor cats.",
    "medication_policy": "Refill requests submitted through the portal or by phone with 48 hours notice. Pickup Mon–Fri 8am–6pm, Sat 9am–2pm. Controlled substances require an in-person visit within the last 12 months.",
    "new_client_policy": "New clients are welcome. Please bring prior medical records or ask us to request them from your previous clinic.",
    "deposit_policy": "No deposit required for standard exams. $50 deposit to hold surgical consult slots.",
    "faqs": [
        {"q": "Do you see rabbits or reptiles?", "a": "We currently see dogs and cats only. For exotic species we can refer you to a nearby exotics-certified clinic."},
        {"q": "Do you offer boarding?", "a": "We don't offer boarding — we can recommend trusted local partners."},
        {"q": "Do you take insurance?", "a": "We collect payment at the visit and provide an itemized invoice you can submit to your pet insurance for reimbursement."},
    ],
    "greeting": "Hi! I'm the front-desk assistant. I can answer questions about hours, pricing, vaccines, and help you book an appointment. What can I help you with today?",
}


async def get_or_create_receptionist_config(clinic_id: str) -> dict:
    cfg = await db.receptionist_configs.find_one({"clinic_id": clinic_id}, {"_id": 0})
    if not cfg:
        clinic = await db.clinics.find_one({"clinic_id": clinic_id}, {"_id": 0}) or {}
        cfg = {"clinic_id": clinic_id, "clinic_name": clinic.get("name", "our clinic"), **DEFAULT_RECEPTIONIST,
               "created_at": datetime.now(timezone.utc).isoformat()}
        await db.receptionist_configs.insert_one(cfg)
        cfg.pop("_id", None)
    else:
        clinic = await db.clinics.find_one({"clinic_id": clinic_id}, {"_id": 0}) or {}
        cfg["clinic_name"] = clinic.get("name", cfg.get("clinic_name", "our clinic"))
        cfg["primary_color"] = clinic.get("primary_color", "#236349")
        cfg["logo_url"] = clinic.get("logo_url")
    return cfg


@api.get("/receptionist/config")
async def receptionist_config_get(user=Depends(auth_dep)):
    return await get_or_create_receptionist_config(user["clinic_id"])


@api.patch("/receptionist/config")
async def receptionist_config_patch(req: ReceptionistConfigReq, user=Depends(auth_dep)):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No changes")
    await get_or_create_receptionist_config(user["clinic_id"])  # ensure exists
    await db.receptionist_configs.update_one({"clinic_id": user["clinic_id"]}, {"$set": updates})
    await audit(user, "receptionist_config_updated", metadata={k: (v if not isinstance(v, list) else f"{len(v)} items") for k, v in updates.items()})
    return await db.receptionist_configs.find_one({"clinic_id": user["clinic_id"]}, {"_id": 0})


@api.get("/receptionist/public/{clinic_id}")
async def receptionist_public_config(clinic_id: str):
    """Public — chat widget bootstraps here. Returns only display-safe fields."""
    cfg = await get_or_create_receptionist_config(clinic_id)
    if not cfg.get("enabled", True):
        raise HTTPException(404, "Receptionist not available")
    return {
        "clinic_name": cfg.get("clinic_name"),
        "primary_color": cfg.get("primary_color", "#236349"),
        "logo_url": cfg.get("logo_url"),
        "greeting": cfg.get("greeting"),
        "hours_text": cfg.get("hours_text"),
        "address": cfg.get("address"),
        "emergency_phone": cfg.get("emergency_phone"),
    }


@api.post("/receptionist/chat")
async def receptionist_chat(req: ReceptionistChatReq):
    """Public. Runs the AI receptionist against the clinic's approved config."""
    cfg = await get_or_create_receptionist_config(req.clinic_id)
    if not cfg.get("enabled", True):
        raise HTTPException(404, "Receptionist not available")

    # Load or create chat session
    session = await db.receptionist_sessions.find_one({"session_id": req.session_id, "clinic_id": req.clinic_id}, {"_id": 0})
    if not session:
        session = {
            "session_id": req.session_id,
            "clinic_id": req.clinic_id,
            "transcript": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "handed_off": False,
            "status": "active",
        }
        await db.receptionist_sessions.insert_one(session)

    transcript = session.get("transcript", [])

    # Deterministic emergency-keyword safety net (belt & suspenders)
    kw = emergency_keyword_hit(req.message)

    resp = await receptionist_reply(cfg, transcript, req.message)
    if kw:
        resp["handoff"] = "urgent"
        resp["emergency_detected"] = True
        resp["reply"] = cfg.get("emergency_instructions", resp.get("reply", ""))

    # Persist turns
    transcript.append({"role": "user", "text": req.message, "at": datetime.now(timezone.utc).isoformat()})
    transcript.append({"role": "assistant", "text": resp.get("reply", ""), "at": datetime.now(timezone.utc).isoformat(),
                       "meta": {"handoff": resp.get("handoff"), "intent": resp.get("detected_intent"), "emergency": resp.get("emergency_detected", False)}})
    await db.receptionist_sessions.update_one(
        {"session_id": req.session_id, "clinic_id": req.clinic_id},
        {"$set": {"transcript": transcript, "last_activity": datetime.now(timezone.utc).isoformat(),
                  "handed_off": resp.get("handoff") in ("needed", "urgent") or session.get("handed_off", False)}},
    )

    # If handoff, create a clinic-inbox message + task
    if resp.get("handoff") in ("needed", "urgent") and not session.get("handed_off"):
        convo_summary = "\n".join(f"{t['role'].upper()}: {t['text']}" for t in transcript[-6:])
        subject = "AI Receptionist: URGENT — possible emergency" if resp.get("handoff") == "urgent" else f"AI Receptionist: {resp.get('detected_intent','handoff')}"
        msg_doc = {
            "id": str(uuid.uuid4()),
            "clinic_id": req.clinic_id,
            "owner_id": None,
            "patient_id": None,
            "received_at": datetime.now(timezone.utc).isoformat(),
            "channel": "Website chat",
            "subject": subject,
            "body": f"AI Receptionist handoff from session {req.session_id}. Reason: {resp.get('handoff_reason','')}.\n\nRecent turns:\n{convo_summary}",
            "status": "new",
            "category": "urgent_review" if resp.get("handoff") == "urgent" else "appointment_needed",
            "draft": None,
        }
        await db.messages.insert_one(msg_doc)
        await create_task(
            db, req.clinic_id, None,
            title=("URGENT — website chat needs a human NOW" if resp.get("handoff") == "urgent" else f"Website chat handoff — {resp.get('detected_intent','follow up')}"),
            description=convo_summary[:400],
            priority=("urgent" if resp.get("handoff") == "urgent" else "high"),
            source="receptionist_handoff", source_id=req.session_id,
        )

    return {
        "reply": resp.get("reply"),
        "handoff": resp.get("handoff", "none"),
        "emergency_detected": resp.get("emergency_detected", False),
        "detected_intent": resp.get("detected_intent"),
        "collected": resp.get("collected", {}),
        "booking_ready": resp.get("booking_ready", False),
    }


@api.post("/receptionist/book")
async def receptionist_book(req: ReceptionistBookReq):
    """Public — request an appointment booking. Creates an appointment_request task in the clinic inbox for staff to confirm."""
    cfg = await get_or_create_receptionist_config(req.clinic_id)
    # Basic rule check: species must be accepted
    if req.species not in (cfg.get("species") or []):
        raise HTTPException(400, f"We currently see: {', '.join(cfg.get('species', []))}. A staff member will follow up if we can refer you.")

    booking_id = str(uuid.uuid4())
    body = (
        f"New website booking request from {req.owner_name} ({req.owner_phone}).\n"
        f"Pet: {req.pet_name} ({req.species}{', '+req.breed if req.breed else ''}{', age '+req.age if req.age else ''}).\n"
        f"Reason: {req.reason}\n"
        f"Preferred time: {req.preferred_time or 'flexible'}"
    )
    msg_doc = {
        "id": str(uuid.uuid4()),
        "clinic_id": req.clinic_id,
        "owner_id": None,
        "patient_id": None,
        "received_at": datetime.now(timezone.utc).isoformat(),
        "channel": "Website chat",
        "subject": f"AI Receptionist booking: {req.pet_name} — {req.reason[:40]}",
        "body": body,
        "status": "new",
        "category": "appointment_needed",
        "draft": None,
        "booking": {
            "id": booking_id,
            "pet_name": req.pet_name, "species": req.species, "breed": req.breed, "age": req.age,
            "reason": req.reason, "owner_name": req.owner_name, "owner_phone": req.owner_phone,
            "preferred_time": req.preferred_time,
        },
    }
    await db.messages.insert_one(msg_doc)
    await create_task(
        db, req.clinic_id, None,
        title=f"Confirm website booking — {req.pet_name}",
        description=body[:400],
        priority="high", source="receptionist_booking", source_id=booking_id, due_days=1,
    )
    await db.receptionist_sessions.update_one(
        {"session_id": req.session_id, "clinic_id": req.clinic_id},
        {"$set": {"booking_created": True, "booking_id": booking_id, "status": "booked"}}, upsert=True,
    )
    return {"ok": True, "booking_id": booking_id}


@api.get("/receptionist/sessions")
async def receptionist_sessions(user=Depends(auth_dep)):
    sessions = [clean(s) for s in await db.receptionist_sessions.find({"clinic_id": user["clinic_id"]}).sort("last_activity", -1).to_list(200)]
    return sessions


# ---------- Wire routers ----------
app.include_router(api)
app.include_router(build_auth_routes(db))
app.include_router(build_stripe_routes(db, auth_dep))

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
