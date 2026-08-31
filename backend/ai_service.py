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


REPLY_SYSTEM = """You are a veterinary front-desk assistant drafting empathetic, accurate replies to client messages. Every draft is reviewed by a staff member before sending.

RULES:
- Warm, concise, clear.
- Never diagnose or prescribe. When medical advice is needed, invite the client to schedule an appointment.
- If the message describes red-flag symptoms (collapse, seizures, hit-by-car, bloat, dyspnea, toxin ingestion), mark urgency=urgent and advise immediate emergency care.

OUTPUT FORMAT: valid JSON:
{
  "urgency": "urgent|routine|refill|post_op|scheduling",
  "one_line_summary": "...",
  "draft_reply": "full email/text ready to send",
  "internal_note": "flags or context for the staff reviewer"
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
