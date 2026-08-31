"""AI service: Claude Sonnet 5 for SOAP/differentials/discharge + Whisper for transcription."""
import os
import json
import re
import uuid
import logging
from typing import Optional
from emergentintegrations.llm.chat import LlmChat, UserMessage
from emergentintegrations.llm.openai import OpenAISpeechToText

logger = logging.getLogger(__name__)
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")

CLAUDE_MODEL = "claude-sonnet-5"
CLAUDE_PROVIDER = "anthropic"


def _extract_json(text: str) -> dict:
    """Extract first JSON object from LLM output. Falls back to raw text."""
    text = text.strip()
    # strip markdown fences
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    # find first balanced JSON object
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass
    return {"raw": text}


async def _claude_call(system: str, user_text: str, session_id: Optional[str] = None) -> str:
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=session_id or f"vetaura-{uuid.uuid4().hex[:8]}",
        system_message=system,
    ).with_model(CLAUDE_PROVIDER, CLAUDE_MODEL)
    resp = await chat.send_message(UserMessage(text=user_text))
    return resp if isinstance(resp, str) else str(resp)


async def transcribe_audio(file_bytes: bytes, filename: str = "audio.webm") -> str:
    """Transcribe audio using OpenAI Whisper via Emergent Universal Key."""
    stt = OpenAISpeechToText(api_key=EMERGENT_LLM_KEY)
    import io
    audio_file = io.BytesIO(file_bytes)
    audio_file.name = filename
    resp = await stt.transcribe(
        file=audio_file,
        model="whisper-1",
        response_format="json",
    )
    return resp.text if hasattr(resp, "text") else str(resp)


SOAP_SYSTEM = """You are Vetaura, an expert veterinary clinical documentation assistant. You draft SOAP notes from raw appointment transcripts.

CRITICAL RULES:
- You produce DRAFTS only. The veterinarian must review and sign every note.
- Preserve clinical accuracy. Never invent findings not present in the transcript.
- Use veterinary terminology (e.g., "T 39.1°C", "HR 120bpm", "BCS 6/9", "MM pink, CRT <2s").
- If information is missing for a section, write "Not documented in transcript."

OUTPUT FORMAT: Return ONLY valid JSON, no markdown:
{
  "subjective": "chief complaint, history, owner report",
  "objective": "vitals, physical exam findings",
  "assessment": "clinical impressions and problem list",
  "plan": "diagnostics, treatment, medications, recheck, client education",
  "confidence": "high|medium|low",
  "flags": ["any red-flag findings the vet must verify"]
}"""


async def generate_soap(transcript: str, patient_context: str = "") -> dict:
    user = f"""Patient context:
{patient_context or 'Not provided.'}

Appointment transcript:
{transcript}

Draft the SOAP note as JSON only."""
    raw = await _claude_call(SOAP_SYSTEM, user)
    return _extract_json(raw)


DIFF_SYSTEM = """You are a veterinary clinical decision support assistant. Given signalment, history, and exam findings, produce a transparent differential diagnosis checklist for the veterinarian to review.

RULES:
- This is DECISION SUPPORT, not an autonomous diagnosis.
- Include species/breed-specific considerations.
- List 4-8 differentials sorted by likelihood.
- For each: name, likelihood tier (Likely / Secondary / Rare-but-important), one-line rationale, and recommended next diagnostic.

OUTPUT FORMAT: valid JSON only, no markdown:
{
  "differentials": [
    {"name": "...", "tier": "Likely", "rationale": "...", "next_step": "..."}
  ],
  "recommended_workup": ["CBC/Chem", "Urinalysis", "..."],
  "questions_to_ask_owner": ["...", "..."],
  "red_flags": ["..."]
}"""


async def generate_differentials(signalment: str, complaint: str, findings: str) -> dict:
    user = f"""Signalment: {signalment}
Presenting complaint: {complaint}
Exam findings: {findings}

Return the differential checklist as JSON only."""
    raw = await _claude_call(DIFF_SYSTEM, user)
    return _extract_json(raw)


DISCHARGE_SYSTEM = """You are a veterinary client-education writer. Convert clinician-approved plan notes into plain-language discharge instructions for pet owners.

RULES:
- 6th-grade reading level. Warm, calm, respectful.
- Do NOT diagnose or change the plan.
- Structure: what happened today, medications (with schedule), home care, warning signs (Call the clinic immediately if...), recheck info.
- If language is not English, translate the whole output; keep drug names in original.

OUTPUT FORMAT: valid JSON only:
{
  "greeting": "...",
  "summary": "...",
  "medications": [{"name": "...", "dose": "...", "frequency": "...", "duration": "...", "notes": "..."}],
  "home_care": ["...", "..."],
  "warning_signs": ["...", "..."],
  "recheck": "...",
  "closing": "..."
}"""


async def generate_discharge(pet_name: str, plan_notes: str, language: str = "English") -> dict:
    user = f"""Pet name: {pet_name}
Clinician plan notes:
{plan_notes}

Target language: {language}

Return the discharge instructions as JSON only."""
    raw = await _claude_call(DISCHARGE_SYSTEM, user)
    return _extract_json(raw)


REPLY_SYSTEM = """You are a veterinary front-desk assistant that CLASSIFIES incoming client messages AND drafts empathetic, accurate replies. Every draft is reviewed by a staff member before sending.

CLASSIFICATION RULES — return exactly one of these categories:
- "urgent_review": possible medical emergency, red-flag symptoms (collapse, seizures, dyspnea, bloat, uncontrolled bleeding, toxin ingestion, hit-by-car, non-responsive, sustained vomiting/diarrhea)
- "appointment_needed": symptoms or concerns that require an in-person visit but are NOT emergent
- "refill_request": prescription refill or renewal request
- "lab_follow_up": question about recent lab results, imaging, biopsy, cytology
- "medication_question": how-to-give, side effects, missed doses, drug interactions
- "billing": pricing, invoice, insurance, payment questions
- "routine": scheduling, hours, general info, thank-you notes, non-medical

REPLY RULES:
- Warm, concise, clear. Never diagnose or prescribe.
- If urgent_review: draft MUST advise immediate emergency care and provide the clinic's emergency instructions.
- Otherwise invite an appointment when medical advice is needed.

OUTPUT FORMAT: valid JSON only, no markdown:
{
  "category": "urgent_review|appointment_needed|refill_request|lab_follow_up|medication_question|billing|routine",
  "urgency": "urgent|routine|refill|post_op|scheduling",
  "one_line_summary": "...",
  "draft_reply": "full email/text ready to send",
  "internal_note": "flags or context for the staff reviewer",
  "suggests_task": "optional follow-up task title if a staff task should be created"
}"""


async def draft_reply(client_message: str, patient_context: str = "") -> dict:
    user = f"""Patient context:
{patient_context or 'Not provided.'}

Client message:
{client_message}

Return the draft as JSON only."""
    raw = await _claude_call(REPLY_SYSTEM, user)
    return _extract_json(raw)


HANDOFF_SYSTEM = """You are drafting a shift-change handoff for the incoming veterinary team. Be crisp, structured, prioritized.

OUTPUT FORMAT: valid JSON:
{
  "shift_summary": "1-2 sentence overview of active caseload",
  "hospitalized_patients": [
    {"name": "...", "problem": "...", "status": "stable|watch|critical", "pending": "labs/meds/tasks", "next_action": "..."}
  ],
  "pending_labs": ["..."],
  "owner_concerns": ["..."],
  "priority_tasks": ["..."]
}"""


async def generate_handoff(cases_summary: str) -> dict:
    user = f"""Active cases and status:
{cases_summary}

Return the handoff summary as JSON only."""
    raw = await _claude_call(HANDOFF_SYSTEM, user)
    return _extract_json(raw)


# ---------- AI Vet Receptionist ----------
RECEPTIONIST_SYSTEM_TEMPLATE = """You are the Vetaura AI Receptionist for {clinic_name}. You are talking to a pet parent via the website chat.

STRICT RULES — NEVER BREAK THESE:
- You ONLY answer from the clinic's approved information below. If a question is outside that scope OR is medical advice, respond politely that a staff member will follow up, and set handoff=needed.
- You NEVER diagnose, recommend medications, or give clinical advice.
- If the user describes a medical emergency (collapse, seizure, uncontrolled bleeding, difficulty breathing, hit by car, toxin ingestion, blocked cat, sustained vomiting, non-responsive), IMMEDIATELY tell them: "{emergency_instructions}" AND set handoff=urgent.
- You may ONLY book appointments within the clinic's rules below. If the request violates a rule, explain politely and set handoff=needed.
- Keep replies short (2–4 sentences), warm, and clear.

CLINIC APPROVED INFO:
- Hours: {hours}
- Emergency phone: {emergency_phone}
- Address: {address}
- Species accepted: {species}
- Appointment types offered: {appt_types}
- Pricing ranges (owner may ask): {pricing}
- Vaccine requirements: {vaccines}
- Medication pickup policy: {medication_policy}
- New-client policy: {new_client_policy}
- Deposit required: {deposit_policy}
- Approved FAQs: {faqs}

BOOKING FLOW:
When user wants to book, collect (in order): pet name, species, breed, age, reason for visit, owner name, owner phone, preferred day/time. Confirm the summary. Set booking_ready=true only when all fields are collected AND the request fits the rules.

OUTPUT FORMAT — return ONLY valid JSON, no markdown:
{{
  "reply": "warm, short response to the user",
  "handoff": "none|needed|urgent",
  "handoff_reason": "short reason for staff if handoff!=none",
  "emergency_detected": true|false,
  "detected_intent": "faq|hours|pricing|book_appointment|refill|emergency|other",
  "collected": {{"pet_name": null, "species": null, "breed": null, "age": null, "reason": null, "owner_name": null, "owner_phone": null, "preferred_time": null}},
  "booking_ready": false
}}"""


async def receptionist_reply(clinic_config: dict, transcript: list[dict], user_message: str) -> dict:
    """Generate the AI receptionist reply.
    transcript: [{'role': 'user'|'assistant', 'text': '...'}, ...] prior turns
    """
    cfg = clinic_config or {}
    system = RECEPTIONIST_SYSTEM_TEMPLATE.format(
        clinic_name=cfg.get("clinic_name", "our clinic"),
        emergency_instructions=cfg.get("emergency_instructions", "Please hang up and call your nearest emergency veterinary hospital immediately, or call us at the emergency phone number below."),
        emergency_phone=cfg.get("emergency_phone", "(not configured)"),
        hours=cfg.get("hours_text", "Mon–Fri 8am–6pm; Sat 9am–2pm; closed Sun"),
        address=cfg.get("address", "(address on file)"),
        species=", ".join(cfg.get("species", ["Canine", "Feline"])),
        appt_types=", ".join(cfg.get("appt_types", ["Wellness exam", "Sick visit", "Vaccine", "Recheck"])),
        pricing=cfg.get("pricing_text", "Wellness exam $75–$120; Vaccines $35–$65; Dental cleaning $450–$900."),
        vaccines=cfg.get("vaccine_requirements", "Rabies + DA2PP for dogs; Rabies + FVRCP for cats. Boosters annually or every 3 years depending on vaccine."),
        medication_policy=cfg.get("medication_policy", "Refill requests need 48 hours notice. Pickup Mon–Fri 8am–6pm."),
        new_client_policy=cfg.get("new_client_policy", "New clients welcome. Please bring prior records if available."),
        deposit_policy=cfg.get("deposit_policy", "No deposit for standard exams. $50 deposit for surgical consults."),
        faqs="; ".join(f"Q: {f.get('q')} A: {f.get('a')}" for f in cfg.get("faqs", [])),
    )

    conv_lines = []
    for t in transcript[-8:]:
        role = "PET PARENT" if t.get("role") == "user" else "RECEPTIONIST"
        conv_lines.append(f"{role}: {t.get('text','')}")
    conv_lines.append(f"PET PARENT: {user_message}")
    conv_text = "\n".join(conv_lines)

    user = f"Conversation so far:\n{conv_text}\n\nRespond as the receptionist. Return JSON only."
    raw = await _claude_call(system, user, session_id=f"vetaura-recept-{uuid.uuid4().hex[:8]}")
    return _extract_json(raw)
