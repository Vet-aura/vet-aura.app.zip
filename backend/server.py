"""Vetaura backend — FastAPI + MongoDB + Claude Sonnet 5 + Whisper."""
from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os, logging, uuid
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from ai_service import (
    transcribe_audio, generate_soap, generate_differentials,
    generate_discharge, draft_reply, generate_handoff,
)
from seed_data import build_seed

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("vetaura")

mongo_url = os.environ["MONGO_URL"]
mongo = AsyncIOMotorClient(mongo_url)
db = mongo[os.environ["DB_NAME"]]

app = FastAPI(title="Vetaura API")
api = APIRouter(prefix="/api")


# ---------- Models ----------
class SoapReq(BaseModel):
    transcript: str
    patient_id: Optional[str] = None

class TranscriptOnlyReq(BaseModel):
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

class ReplyReq(BaseModel):
    message_id: Optional[str] = None
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
    signed_by: Optional[str] = None


# ---------- Seed on startup ----------
@app.on_event("startup")
async def seed_if_empty():
    if await db.patients.count_documents({}) == 0:
        seed = build_seed()
        await db.owners.insert_many(seed["owners"])
        await db.patients.insert_many(seed["patients"])
        await db.visits.insert_many(seed["visits"])
        await db.labs.insert_many(seed["labs"])
        await db.weights.insert_many(seed["weights"])
        await db.appointments.insert_many(seed["appointments"])
        await db.messages.insert_many(seed["messages"])
        logger.info("Vetaura demo data seeded.")


@app.on_event("shutdown")
async def shutdown():
    mongo.close()


def clean(doc):
    if not doc:
        return doc
    doc.pop("_id", None)
    return doc


# ---------- Basic ----------
@api.get("/")
async def root():
    return {"service": "Vetaura", "status": "ok"}


@api.get("/stats")
async def stats():
    return {
        "patients": await db.patients.count_documents({}),
        "appointments_today": await db.appointments.count_documents({}),
        "open_messages": await db.messages.count_documents({"status": "new"}),
        "signed_notes": await db.soap_notes.count_documents({"signed_by": {"$ne": None}}),
        "draft_notes": await db.soap_notes.count_documents({"signed_by": None}),
    }


# ---------- Owners / Patients ----------
@api.get("/owners")
async def list_owners():
    return [clean(o) for o in await db.owners.find({}).to_list(500)]


@api.get("/patients")
async def list_patients():
    patients = [clean(p) for p in await db.patients.find({}).to_list(500)]
    owners = {o["id"]: o for o in [clean(x) for x in await db.owners.find({}).to_list(500)]}
    for p in patients:
        p["owner"] = owners.get(p.get("owner_id"))
    return patients


@api.get("/patients/{pid}")
async def get_patient(pid: str):
    p = clean(await db.patients.find_one({"id": pid}))
    if not p:
        raise HTTPException(404, "Patient not found")
    p["owner"] = clean(await db.owners.find_one({"id": p.get("owner_id")}))
    p["visits"] = [clean(v) for v in await db.visits.find({"patient_id": pid}).sort("date", -1).to_list(200)]
    p["labs"] = sorted([clean(l) for l in await db.labs.find({"patient_id": pid}).to_list(200)], key=lambda x: x["date"])
    p["weights"] = sorted([clean(w) for w in await db.weights.find({"patient_id": pid}).to_list(200)], key=lambda x: x["date"])
    p["soap_notes"] = [clean(s) for s in await db.soap_notes.find({"patient_id": pid}).sort("created_at", -1).to_list(200)]
    return p


# ---------- Appointments ----------
@api.get("/appointments")
async def list_appointments():
    apts = [clean(a) for a in await db.appointments.find({}).sort("datetime", 1).to_list(200)]
    pats = {p["id"]: p for p in [clean(x) for x in await db.patients.find({}).to_list(500)]}
    owners = {o["id"]: o for o in [clean(x) for x in await db.owners.find({}).to_list(500)]}
    for a in apts:
        pat = pats.get(a.get("patient_id"), {})
        a["patient"] = pat
        a["owner"] = owners.get(pat.get("owner_id"))
    return apts


# ---------- Messages / Inbox ----------
@api.get("/messages")
async def list_messages():
    msgs = [clean(m) for m in await db.messages.find({}).sort("received_at", -1).to_list(200)]
    pats = {p["id"]: p for p in [clean(x) for x in await db.patients.find({}).to_list(500)]}
    owners = {o["id"]: o for o in [clean(x) for x in await db.owners.find({}).to_list(500)]}
    for m in msgs:
        m["patient"] = pats.get(m.get("patient_id"))
        m["owner"] = owners.get(m.get("owner_id"))
    return msgs


@api.post("/messages/{mid}/draft")
async def message_draft(mid: str):
    m = await db.messages.find_one({"id": mid})
    if not m:
        raise HTTPException(404, "Message not found")
    pat = await db.patients.find_one({"id": m.get("patient_id")}) or {}
    context = f"Pet: {pat.get('name')} — {pat.get('species')} — {pat.get('breed')}, age {pat.get('age_years')}. Active problems: {', '.join(pat.get('active_problems', []))}."
    draft = await draft_reply(m["body"], context)
    await db.messages.update_one({"id": mid}, {"$set": {"draft": draft}})
    return draft


@api.post("/messages/{mid}/approve")
async def message_approve(mid: str):
    await db.messages.update_one({"id": mid}, {"$set": {"status": "sent"}})
    return {"ok": True}


# ---------- Ambient Scribe: transcription + SOAP ----------
@api.post("/scribe/transcribe")
async def scribe_transcribe(audio: UploadFile = File(...)):
    data = await audio.read()
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(413, "Audio must be under 25 MB")
    text = await transcribe_audio(data, filename=audio.filename or "audio.webm")
    return {"transcript": text}


@api.post("/scribe/soap")
async def scribe_soap(req: SoapReq):
    context = ""
    if req.patient_id:
        pat = await db.patients.find_one({"id": req.patient_id})
        if pat:
            context = f"Pet: {pat['name']} — {pat['species']} — {pat['breed']}, age {pat['age_years']}, {pat.get('sex','')}, {pat.get('weight_kg','?')}kg. Active problems: {', '.join(pat.get('active_problems', []))}."
    result = await generate_soap(req.transcript, context)
    return result


@api.post("/scribe/save")
async def scribe_save(req: SoapSaveReq):
    doc = {
        "id": str(uuid.uuid4()),
        "patient_id": req.patient_id,
        "appointment_id": req.appointment_id,
        "subjective": req.subjective,
        "objective": req.objective,
        "assessment": req.assessment,
        "plan": req.plan,
        "signed_by": req.signed_by,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.soap_notes.insert_one(doc)
    doc.pop("_id", None)
    return doc


# ---------- Differentials ----------
@api.post("/ai/differentials")
async def ai_diffs(req: DifferentialReq):
    return await generate_differentials(req.signalment, req.complaint, req.findings)


# ---------- Discharge ----------
@api.post("/ai/discharge")
async def ai_discharge(req: DischargeReq):
    return await generate_discharge(req.pet_name, req.plan_notes, req.language)


# ---------- Handoff ----------
@api.post("/ai/handoff")
async def ai_handoff(req: HandoffReq):
    if req.cases_summary:
        summary = req.cases_summary
    else:
        pats = [clean(p) for p in await db.patients.find({}).to_list(200)]
        lines = []
        for p in pats:
            lines.append(f"- {p['name']} ({p['species']}, {p['breed']}, {p['age_years']}y): problems={p.get('active_problems', [])}; alerts={p.get('alerts', [])}")
        summary = "\n".join(lines)
    return await generate_handoff(summary)


app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
