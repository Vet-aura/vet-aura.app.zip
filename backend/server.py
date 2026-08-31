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
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from ai_service import (
    transcribe_audio, generate_soap, generate_differentials,
    generate_discharge, draft_reply, generate_handoff,
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
        for coll in ("owners", "patients", "visits", "labs", "weights", "appointments", "messages"):
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
        "open_messages": await db.messages.count_documents({"clinic_id": cid, "status": "new"}),
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
    await db.messages.update_one({"id": mid, "clinic_id": cid}, {"$set": {"draft": draft}})
    await audit(user, "ai_draft_reply", target=mid)
    return draft


@api.post("/messages/{mid}/approve")
async def message_approve(mid: str, user=Depends(auth_dep)):
    await db.messages.update_one({"id": mid, "clinic_id": user["clinic_id"]}, {"$set": {"status": "sent"}})
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
