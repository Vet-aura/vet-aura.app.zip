"""Public 'Try it on your clinic' wizard.

Fetches a clinic's public website, extracts hours/phone/services/address heuristically,
spins up an ephemeral demo clinic (expires in 24h), and returns a receptionist widget URL.
"""
from __future__ import annotations
import re
import uuid
import socket
import ipaddress
import logging
from urllib.parse import urlparse
import httpx
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


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
    """Fetch and parse public clinic site. Returns extracted profile.

    SSRF hardening: resolve host, reject private/loopback/link-local/metadata ranges
    BEFORE the request; also re-validate after any redirect. Only http/https, only
    ports 80/443, size-capped response.
    """
    try:
        html = await _safe_public_fetch(url)
    except HTTPException:
        raise
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


def _is_public_ip(host: str) -> bool:
    """Resolve host and confirm ALL resolved addresses are globally routable public IPs."""
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception:
        return False
    for info in infos:
        sockaddr = info[4]
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return False
        # Reject: private, loopback, link-local (169.254/16 incl. cloud metadata 169.254.169.254),
        # multicast, reserved, unspecified, and site-local IPv6.
        if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
                or ip.is_reserved or ip.is_unspecified):
            return False
        # extra guard: known cloud metadata endpoints (belt and braces)
        if str(ip) in {"169.254.169.254", "fd00:ec2::254", "100.100.100.200"}:
            return False
    return True


def _assert_url_public(url: str):
    """Reject non-http(s) schemes, non-standard ports, and any private-network host."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(400, "Only http(s) URLs are supported.")
    host = parsed.hostname or ""
    if not host:
        raise HTTPException(400, "URL is missing a host.")
    port = parsed.port
    if port and port not in (80, 443):
        raise HTTPException(400, "Only standard http(s) ports 80/443 are supported.")
    if host.lower() in {"localhost", "metadata.google.internal", "metadata"}:
        raise HTTPException(400, "That host is not permitted.")
    # If host is a literal IP, validate directly.
    try:
        ip = ipaddress.ip_address(host)
        if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
                or ip.is_reserved or ip.is_unspecified):
            raise HTTPException(400, "That address range is not permitted.")
    except ValueError:
        # host is a name — resolve it
        if not _is_public_ip(host):
            raise HTTPException(400, "Host resolves to a non-public address and cannot be fetched.")


async def _safe_public_fetch(url: str, max_redirects: int = 5, max_bytes: int = 3 * 1024 * 1024) -> str:
    """SSRF-safe fetcher. Manual redirect loop with per-hop host validation.

    Manual redirect handling is essential — httpx's automatic redirect would follow
    to a public 302 that then points at 169.254.169.254 without re-validating.
    """
    current = url
    for _ in range(max_redirects + 1):
        _assert_url_public(current)
        async with httpx.AsyncClient(timeout=15, follow_redirects=False,
                                     headers={"User-Agent": "VetauraBot/1.0"}) as c:
            r = await c.get(current)
        if r.status_code in (301, 302, 303, 307, 308):
            loc = r.headers.get("location")
            if not loc:
                raise HTTPException(400, "Redirect with no Location header.")
            # Relative or absolute — resolve against current.
            current = str(httpx.URL(current).join(loc))
            continue
        if r.status_code >= 400:
            raise HTTPException(400, f"Upstream returned HTTP {r.status_code}.")
        # cap body size
        content = r.content[:max_bytes]
        try:
            return content.decode(r.encoding or "utf-8", errors="replace")
        except Exception:
            return content.decode("utf-8", errors="replace")
    raise HTTPException(400, "Too many redirects.")


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
