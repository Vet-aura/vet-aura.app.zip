# Vetaura — Clinical AI Copilot for Veterinary Practices

## Original problem statement
Veterinarian AI that helps veterinarians and staff for tedious jobs that take time away from the clients animal themselves, in every appointment. **User asked to turn it into a sellable product.**

## Core principle
Vet-in-the-loop. Every AI output is a DRAFT. A clinician must review and sign before it affects care.

## Users
- Vet clinic owner (signs up, pays, invites staff)
- Veterinarians (draft/sign notes, differentials, handoffs)
- Vet techs / front desk (inbox triage, discharge, schedule)
- Pet owners (receive shareable branded discharge portal — no login)

## Architecture (Feb 2026 · v2 · Sellable SaaS)
- **Backend:** FastAPI + Motor (Async MongoDB). Multi-tenant by `clinic_id` on every doc. Auto-seeds 4 demo patients per new clinic.
- **Auth:** Emergent Google OAuth + email/password JWT (both in one users collection). 7-day sessions.
- **Billing:** Stripe subscriptions (3 plans, 14-day free trial, no card to start). SMP tax mode (Stripe manages tax & compliance, +3.5% per transaction).
- **AI:** Claude Sonnet 5 (SOAP, differentials, discharge, replies, handoffs) + OpenAI Whisper (audio transcription). Emergent Universal Key.
- **Frontend:** React 19 + React Router + shadcn/ui + Tailwind + Recharts + Sonner. Public marketing site, protected app, and public /d/:token owner portal.
- **Design:** Botanical Medical & Warm Precision — Forest greens (#236349), warm amber, sage canvas; Fraunces + Plus Jakarta Sans + JetBrains Mono.

## Implemented (v2 · Feb 2026)

### Marketing & sales
- Landing page with hero, feature grid, compliance strip and CTAs
- **/pricing** — 3 plan cards from Stripe (Solo $49 / Clinic $199 / Multi-site $499)
- **/features** — 10-card deep feature grid
- **/faq** — 9 accordion Q&As
- **/demo** — Book-a-demo form persisted to `demo_requests`

### Auth & multi-tenant
- Email/password signup + login (JWT)
- Emergent Google OAuth (`/api/auth/session` exchange, cookie + Bearer supported)
- `/api/auth/me` for session verification
- Every doc scoped by `clinic_id`; verified 100% data isolation between clinics

### Billing (Stripe)
- 3 subscription products with 14-day free trial
- Checkout session, billing portal, webhook (handles trial start, subscription paid/canceled/updated)
- `/payments/status/{session_id}` fallback polling
- Managed Payments (SMP) tax mode — Stripe handles tax & compliance

### Onboarding
- 3-step wizard: Clinic → Branding (color + footer) → Explore tips
- `onboarded` gate on ProtectedRoute
- Trial banner in sidebar

### Core AI features (from v1, now clinic-scoped + audit-logged)
- Ambient SOAP scribe (mic → Whisper → Claude → sign)
- Differential diagnosis checklist
- Multilingual discharge (6 languages) — now with **shareable owner portal link**
- Inbox triage with urgency tags
- Shift handoff summaries
- Patient records with weight/renal trends

### Sellable extras
- **Audit log** — every AI draft, signature, share, approval, export, clinic update
- **CSV exports** — `/api/export/patients.csv` and `/api/export/notes.csv`
- **Clinic branding** — name, primary color, logo URL, discharge footer
- **Public shareable owner portal** — `/d/:token` renders discharge with clinic branding, medications, warning signs and a "Request recheck" CTA (their #1 revenue-conversion unlock)

## Testing
- Iteration 2: 20/20 backend tests + all critical frontend flows passing
- Test suite at `/app/backend/tests/backend_test.py`
- Auth playbook at `/app/auth_testing.md`

## Test credentials
See `/app/memory/test_credentials.md`. Stripe test card 4242 4242 4242 4242.

## Backlog (P0/P1/P2)
- **P1** Email delivery of discharge PDFs (Resend/SendGrid) — the shareable link is v1
- **P1** Staff invitations (multi-user per clinic beyond owner)
- **P1** Real-time streaming transcript in ambient scribe (currently one-shot upload)
- **P1** PIMS/EMR export in native formats (eVetPractice, Cornerstone, AVImark)
- **P1** SSO for Multi-site plan (SAML/OIDC)
- **P2** Radiograph/x-ray upload + Claude vision triage
- **P2** Vaccine + preventive-care reminder automation (SMS via Twilio, email via Resend)
- **P2** Estimate builder & inventory forecasting
- **P2** Owner-side account (view all discharges, refill requests, book appointments)
