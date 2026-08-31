"""Public 'Try it on your clinic' wizard.

Fetches a clinic's public website, extracts hours/phone/services/address heuristically,
spins up an ephemeral demo clinic (expires in 24h), and returns a receptionist widget URL.
"""
from __future__ import annotations
import re
import uuid
import httpx
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl
from motor.motor_asyncio import AsyncIOMotorDatabase


PHONE_RE = re.compile(r"(?:\+?1[\s.\-]?)?\(?\b\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}\b")
DAY_RE = re.compile(r"(mon|tue|wed|thu|fri|sat|sun)", re.I)
HOURS_LINE_RE = re.compile(
    r"(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*\s*[-–—to]*\s*(?:mon|tue|wed|thu|fri|sat|sun)?[a-z]*\s*[:\-]?\s*\d{1,2}(?::\d{2})?\s*(?:am|pm)?\s*[-–—to]+\s*\d{1,2}(?::\d{2})?\s*(?:am|pm)?",
    re.I,
)
SERVICE_KEYWORDS = [
    "wellness", "vaccine", "vaccination", "dental", "surgery", "spay", "neuter",
    "boarding", "grooming", "microchip", "dermatology", "cardiology", "orthopedic",
    "radiology", "ultrasound", "laser therapy", "acupuncture", "urgent care",
    "senior care", "puppy", "kitten", "nutrition", "behavior",
]


class TryItReq(BaseModel):
    url: HttpUrl
    email: str | None = None


def _strip_tags(html: str) -> str:
    # simple: remove scripts/styles then tags
    html = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    html = re.sub(r"<style[\s\S]*?</style>", " ", html, flags=re.I)
    html = re.sub(r"<[^>]+>", " ", html)
    html = re.sub(r"\s+", " ", html).strip()
    return html


def _extract_title(html: str) -> str | None:
    m = re.search(r"<title[^>]*>([^<]{2,150})</title>", html, re.I)
    if not m:
        return None
    t = re.sub(r"\s+", " ", m.group(1)).strip()
    # trim common suffixes
    t = re.split(r"\s[·|–\-]\s", t)[0].strip()
    return t or None


def _extract_hours(text: str) -> str:
    lines = HOURS_LINE_RE.findall(text)
    if not lines:
        # fallback: find any line with a day + a time
        rough = re.findall(
            r"[A-Za-z]{3,9}(?:\s*[-–—to]+\s*[A-Za-z]{3,9})?[:\s\-]+\d{1,2}(?::\d{2})?\s*(?:am|pm)[^.]{0,40}",
            text,
            re.I,
        )
        lines = [r for r in rough if DAY_RE.search(r)][:5]
    seen: list[str] = []
    for h in lines[:8]:
        h = re.sub(r"\s+", " ", h).strip(" .,;")
        if h and h.lower() not in [s.lower() for s in seen]:
            seen.append(h)
    return " · ".join(seen) if seen else ""


def _extract_services(text: str) -> list[str]:
    tl = text.lower()
    found: list[str] = []
    for kw in SERVICE_KEYWORDS:
        if kw in tl and kw.title() not in found:
            found.append(kw.title())
    return found[:8]


def _extract_address(text: str) -> str:
    # US-style address: number + street + suffix + city, ST ZIP  (require state OR ZIP to avoid false positives)
    m = re.search(
        r"\b\d{2,6}\s+[A-Z][A-Za-z0-9.\- ]{2,40}(?:\bStreet|\bSt\.?|\bAvenue|\bAve\.?|\bRoad|\bRd\.?|\bBoulevard|\bBlvd\.?|\bDrive|\bDr\.?|\bLane|\bLn\.?|\bWay|\bCourt|\bCt\.?|\bParkway|\bPkwy\.?|\bHighway|\bHwy\.?|\bCircle|\bCir\.?|\bTerrace|\bTer\.?|\bPlace|\bPl\.?)[^,]{0,40},\s*[A-Z][A-Za-z .]{2,30},\s*[A-Z]{2}\s*\d{5}",
        text,
    )
    if m:
        return m.group(0).strip()
    # Fallback: number + street + suffix + ZIP within 60 chars
    m = re.search(
        r"\b\d{2,6}\s+[A-Z][A-Za-z0-9.\- ]{2,40}(?:\bStreet|\bSt\.?|\bAvenue|\bAve\.?|\bRoad|\bRd\.?|\bBoulevard|\bBlvd\.?|\bDrive|\bDr\.?|\bLane|\bLn\.?|\bWay|\bParkway|\bPkwy\.?|\bHighway|\bHwy\.?)[^0-9]{0,50}\d{5}\b",
        text,
    )
    return m.group(0).strip() if m else ""


async def scrape_clinic(url: str) -> dict:
    """Fetch and parse public clinic site. Returns extracted profile."""
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers={"User-Agent": "VetauraBot/1.0"}) as c:
            r = await c.get(url)
            r.raise_for_status()
            html = r.text
    except Exception as e:
        raise HTTPException(400, f"Could not load {url}: {e}")

    text = _strip_tags(html)
    title = _extract_title(html) or "Your veterinary clinic"
    phones = list(dict.fromkeys(PHONE_RE.findall(text)))[:2]
    hours = _extract_hours(text)
    services = _extract_services(text)
    address = _extract_address(text)

    profile = {
        "clinic_name": title,
        "hours_text": hours or "Mon–Fri 8am–6pm · Sat 9am–2pm · Closed Sun",
        "emergency_phone": phones[0] if phones else "",
        "address": address or "",
        "appt_types": services or ["Wellness exam", "Sick visit", "Vaccine", "Recheck"],
        "source_url": url,
    }
    return profile


def build_tryit_routes(db: AsyncIOMotorDatabase):
    router = APIRouter(prefix="/api/marketing")

    @router.post("/try-it")
    async def try_it(req: TryItReq):
        profile = await scrape_clinic(str(req.url))
        demo_id = "demo_" + uuid.uuid4().hex[:10]
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()

        # Create ephemeral clinic + receptionist config
        await db.clinics.insert_one({
            "clinic_id": demo_id,
            "name": profile["clinic_name"],
            "plan": "demo",
            "plan_status": "trial",
            "primary_color": "#236349",
            "logo_url": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "demo_expires_at": expires_at,
            "source_url": profile["source_url"],
            "lead_email": req.email,
        })
        cfg = {
            "clinic_id": demo_id,
            "clinic_name": profile["clinic_name"],
            "enabled": True,
            "hours_text": profile["hours_text"],
            "address": profile["address"],
            "emergency_phone": profile["emergency_phone"] or "(please call your local ER vet)",
            "emergency_instructions": (
                "This sounds like an emergency — please head to your nearest emergency veterinary hospital immediately."
                + (f" Or call us at {profile['emergency_phone']}." if profile["emergency_phone"] else "")
            ),
            "species": ["Canine", "Feline"],
            "appt_types": profile["appt_types"],
            "pricing_text": "Please call the clinic for current pricing — this is a demo receptionist.",
            "vaccine_requirements": "Please ask the clinic for their vaccine schedule.",
            "medication_policy": "Refill requests require 48 hours notice.",
            "new_client_policy": "New clients welcome. Please bring prior records if available.",
            "deposit_policy": "Standard exams do not require a deposit.",
            "faqs": [],
            "greeting": f"Hi! I'm the demo AI receptionist for {profile['clinic_name']}. Ask me about hours, services, or booking. Real staff aren't monitoring this demo.",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "demo_expires_at": expires_at,
        }
        await db.receptionist_configs.insert_one(cfg)
        await db.tryit_leads.insert_one({
            "id": str(uuid.uuid4()),
            "email": req.email,
            "url": profile["source_url"],
            "demo_clinic_id": demo_id,
            "profile": profile,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        return {
            "demo_clinic_id": demo_id,
            "profile": profile,
            "receptionist_path": f"/r/{demo_id}",
            "expires_at": expires_at,
        }

    return router
