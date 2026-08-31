"""Clinic-editable SOAP template library.

Templates shape the AI's SOAP output to match a clinic's house style. Each template
provides guidance strings for S/O/A/P plus optional required-fields checklist. Defaults
are lazily seeded per clinic the first time templates are listed.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorDatabase


DEFAULT_TEMPLATES = [
    {
        "slug": "wellness",
        "name": "Wellness / Annual exam",
        "description": "Routine wellness visit, vaccines, preventive care.",
        "subjective_hint": "Include vaccine history, diet, activity, environment, travel, prior illnesses, current preventives (heartworm/flea/tick).",
        "objective_hint": "Full nose-to-tail exam with all systems. Include BCS 1–9, MCS, weight trend, dental grade 0–4, ocular, aural, cardiac auscultation, abdominal palpation, lymph nodes, integument.",
        "assessment_hint": "Overall health status, care gaps (dental, weight, vaccine status), preventive-care recommendations.",
        "plan_hint": "Vaccines administered today with lot #, preventives dispensed with dose, next visit due, client education topics, weight/nutrition plan if applicable.",
        "required_fields": ["BCS", "Weight", "Dental grade", "Vaccine status"],
    },
    {
        "slug": "dental",
        "name": "Dental / COHAT",
        "description": "Comprehensive oral health assessment and treatment.",
        "subjective_hint": "Owner-reported halitosis, chewing changes, dropping food, pawing at mouth, prior dental history.",
        "objective_hint": "Pre-anesthetic vitals, oral exam findings (calculus grade, gingivitis index, missing/fractured teeth, mobility, oronasal fistula, masses). Note anesthesia protocol and monitoring.",
        "assessment_hint": "Dental disease stage, extractions performed with tooth numbers (Triadan), gingivitis grade, biopsies taken.",
        "plan_hint": "Post-op meds (NSAID, opioid, antibiotic), soft-food period, recheck, home-care instructions (brushing, dental chews, water additive).",
        "required_fields": ["Anesthesia protocol", "Teeth extracted", "Radiograph findings"],
    },
    {
        "slug": "dermatology",
        "name": "Dermatology / Otitis",
        "description": "Skin, ear, allergy work-ups and rechecks.",
        "subjective_hint": "Onset, seasonality, pruritus score 0–10, response to prior therapy, diet history, environment, other pets affected.",
        "objective_hint": "Lesion distribution and morphology, otoscopic exam AU (canal erythema, discharge quality, TM status), cytology results (cocci, rods, yeast, neutrophils).",
        "assessment_hint": "Primary diagnosis (atopic dermatitis, otitis externa Malassezia, food-responsive dermatosis, etc.), infection status, allergy phenotype.",
        "plan_hint": "Topical/systemic therapy with duration, cleanser schedule, diet trial if applicable, recheck cytology timing, itch score follow-up.",
        "required_fields": ["Cytology", "Otoscopy AU", "Pruritus score"],
    },
    {
        "slug": "euthanasia",
        "name": "Euthanasia / End-of-life",
        "description": "Compassionate humane euthanasia record.",
        "subjective_hint": "Owner-reported quality-of-life indicators, decision context, family present, aftercare choice (cremation/burial).",
        "objective_hint": "Pre-euthanasia condition, sedation given (drug, dose, route), IV catheter placement, euthanasia solution (dose, route), time of death, cardiac auscultation confirming cessation.",
        "assessment_hint": "Confirmation of humane euthanasia. Include primary underlying condition.",
        "plan_hint": "Aftercare arrangement, paw print / clay impression if provided, condolence follow-up, cremains return timeline, grief support resources shared.",
        "required_fields": ["Sedation protocol", "Time of death", "Aftercare"],
    },
    {
        "slug": "post_op",
        "name": "Post-op recheck",
        "description": "Follow-up after surgical procedure.",
        "subjective_hint": "Owner report on appetite, activity, medication compliance, incision appearance, elimination.",
        "objective_hint": "Vitals, incision assessment (erythema, swelling, discharge, dehiscence), pain score 0–4, ROM if orthopedic.",
        "assessment_hint": "Recovery status (as expected / complication), infection risk, pain control adequacy.",
        "plan_hint": "Continue vs. adjust medications, activity restriction timeline, suture removal date, next recheck window, red-flag warning signs for owner.",
        "required_fields": ["Incision status", "Pain score", "Activity restriction"],
    },
]


class TemplateReq(BaseModel):
    name: str = Field(min_length=1)
    slug: Optional[str] = None
    description: Optional[str] = ""
    subjective_hint: Optional[str] = ""
    objective_hint: Optional[str] = ""
    assessment_hint: Optional[str] = ""
    plan_hint: Optional[str] = ""
    required_fields: Optional[list[str]] = None


class TemplatePatchReq(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    subjective_hint: Optional[str] = None
    objective_hint: Optional[str] = None
    assessment_hint: Optional[str] = None
    plan_hint: Optional[str] = None
    required_fields: Optional[list[str]] = None


async def ensure_templates(db: AsyncIOMotorDatabase, clinic_id: str):
    """Lazily seed the 5 built-in templates on first access per clinic."""
    if await db.soap_templates.count_documents({"clinic_id": clinic_id, "is_default": True}) >= len(DEFAULT_TEMPLATES):
        return
    now = datetime.now(timezone.utc).isoformat()
    for t in DEFAULT_TEMPLATES:
        exists = await db.soap_templates.find_one({"clinic_id": clinic_id, "slug": t["slug"], "is_default": True})
        if exists:
            continue
        await db.soap_templates.insert_one({
            "id": str(uuid.uuid4()),
            "clinic_id": clinic_id,
            **t,
            "is_default": True,
            "created_at": now,
            "updated_at": now,
        })


async def get_template(db: AsyncIOMotorDatabase, clinic_id: str, template_id: str) -> Optional[dict]:
    doc = await db.soap_templates.find_one({"id": template_id, "clinic_id": clinic_id}, {"_id": 0})
    return doc


def template_prompt_block(template: dict | None) -> str:
    """Render a template into a prompt-injectable guidance block."""
    if not template:
        return ""
    lines = [f"CLINIC TEMPLATE — {template['name']} (follow this house style):"]
    for label, key in [("Subjective guidance", "subjective_hint"), ("Objective guidance", "objective_hint"),
                       ("Assessment guidance", "assessment_hint"), ("Plan guidance", "plan_hint")]:
        v = (template.get(key) or "").strip()
        if v:
            lines.append(f"- {label}: {v}")
    req = template.get("required_fields") or []
    if req:
        lines.append("- Fields that MUST be addressed (mark 'Not documented in transcript.' if absent): " + ", ".join(req))
    return "\n".join(lines)


def build_template_routes(db: AsyncIOMotorDatabase, auth_dep):
    router = APIRouter(prefix="/api/scribe/templates")

    @router.get("")
    async def list_templates(user=Depends(auth_dep)):
        cid = user["clinic_id"]
        await ensure_templates(db, cid)
        items = await db.soap_templates.find({"clinic_id": cid}, {"_id": 0}).sort([("is_default", -1), ("name", 1)]).to_list(200)
        return items

    @router.post("")
    async def create_template(req: TemplateReq, user=Depends(auth_dep)):
        cid = user["clinic_id"]
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "id": str(uuid.uuid4()),
            "clinic_id": cid,
            "slug": req.slug or req.name.lower().replace(" ", "_")[:32],
            **req.model_dump(exclude_none=True),
            "is_default": False,
            "created_at": now,
            "updated_at": now,
        }
        await db.soap_templates.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.patch("/{tid}")
    async def update_template(tid: str, req: TemplatePatchReq, user=Depends(auth_dep)):
        updates = {k: v for k, v in req.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(400, "No changes")
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        r = await db.soap_templates.update_one({"id": tid, "clinic_id": user["clinic_id"]}, {"$set": updates})
        if r.matched_count == 0:
            raise HTTPException(404, "Template not found")
        return await db.soap_templates.find_one({"id": tid, "clinic_id": user["clinic_id"]}, {"_id": 0})

    @router.delete("/{tid}")
    async def delete_template(tid: str, user=Depends(auth_dep)):
        doc = await db.soap_templates.find_one({"id": tid, "clinic_id": user["clinic_id"]})
        if not doc:
            raise HTTPException(404, "Template not found")
        if doc.get("is_default"):
            raise HTTPException(400, "Built-in templates cannot be deleted. Edit or hide them instead.")
        await db.soap_templates.delete_one({"id": tid, "clinic_id": user["clinic_id"]})
        return {"ok": True}

    return router
