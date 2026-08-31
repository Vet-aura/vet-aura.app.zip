# Vetaura — Clinical AI Copilot for Veterinary Practices

## Original problem statement
Veterinarian AI that helps veterinarians and staff for tedious jobs that take time away from the clients animal themselves, in every appointment.

## Users
- Veterinarians (primary): draft notes, get differentials, sign records, hand off shifts
- Vet techs / front desk: triage client messages, generate discharge instructions, manage schedule
- Owners (indirectly): receive plain-language, multilingual discharge summaries

## Core principle
Vet-in-the-loop. Every AI output is a DRAFT. A clinician must review and sign before it affects care.

## Architecture (v1 — Feb 2026)
- **Backend:** FastAPI + Motor (Async MongoDB). Auto-seeds veterinary demo data on empty DB.
- **AI:** Claude Sonnet 5 (SOAP, differentials, discharge, reply drafts, handoff) + OpenAI Whisper (audio transcription). Both via Emergent Universal LLM Key.
- **Frontend:** React 19 + React Router + shadcn/ui + Tailwind + Recharts + Sonner toasts.
- **Design:** Botanical Medical & Warm Precision — Forest greens (#236349), warm amber accents, sage canvas; Fraunces serif headings + Plus Jakarta Sans UI + JetBrains Mono clinical data.

## Implemented (Feb 2026)
- Landing page with clinical value prop, hero and 4 feature cards
- Clinic dashboard (KPIs, today's schedule, alerts, message previews)
- **Ambient SOAP scribe (flagship):** mic recording → Whisper → editable transcript → Claude Sonnet 5 drafts S/O/A/P → vet reviews and signs → filed to patient record. Sample transcripts included so demo runs without mic permission.
- Patient records: list + detail with tabs (Visits, Trends, Labs, Notes); weight + renal panel line charts (Recharts); out-of-range labs highlighted.
- Differential diagnosis generator with tier badges, workup, questions and red flags; 3 pre-built templates.
- Discharge instruction generator (multilingual — 6 languages) with medications, home care, warning signs, recheck.
- Client inbox triage: AI-drafted replies with urgency tagging (urgent/routine/refill/post_op/scheduling).
- Shift handoff summary aggregating all active patients into hospitalized cases, pending labs, owner concerns, priority tasks.
- Schedule view with shadcn calendar + daily appointment list.
- Seeded demo data: 4 owners, 4 patients (Bella, Milo, Luna, Ollie), visits, longitudinal labs (Milo CKD trend), weights, 4 today-appointments, 4 client messages.

## Backlog (P0/P1/P2)
- **P0** Auth — Emergent Google login + JWT staff accounts (deferred from MVP)
- **P0** Image/PDF upload for radiographs & lab reports (Emergent object storage)
- **P1** Ambient scribe: real-time streaming transcript (currently one-shot upload)
- **P1** PIMS/EMR export — one-click "copy to eVetPractice / Cornerstone / AVImark" format
- **P1** Appointment scheduling: create/edit/reschedule + double-booking flag
- **P1** Vaccine + preventive-care reminder automation (email/SMS via SendGrid or Resend)
- **P2** Imaging triage — attach radiograph and ask Claude to flag possible abnormalities
- **P2** Estimate builder / inventory forecasting / operations analytics dashboard
- **P2** Multi-clinic support & role-based access
- **P2** Owner portal for approved discharge instructions delivery

## Test credentials
None — v1 runs in single-clinic demo mode (no auth).
