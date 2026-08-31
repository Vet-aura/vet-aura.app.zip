# Vetaura — Clinical AI Copilot for Veterinary Practices

## Original problem statement
Veterinarian AI that helps veterinarians and staff for tedious jobs that take time away from the clients' animals during every appointment. **User asked to turn it into a sellable product** — multi-tenant SaaS with billing, marketing site, phone/SMS receptionist, ambient scribe, and Try-it-on-your-clinic public onboarding.

## Core principle
Vet-in-the-loop. Every AI output is a DRAFT. A clinician must review and sign before it affects care.

## Users
- Vet clinic owner (signs up, pays, invites staff)
- Veterinarians (draft/sign notes, differentials, handoffs)
- Vet techs / front desk (inbox triage, discharge, schedule)
- Pet owners (receive shareable branded discharge portal — no login)

## Architecture (Feb 2026 · v3 · Voice + Templates)
- **Backend:** FastAPI + Motor (Async MongoDB). Multi-tenant by `clinic_id` on every doc.
- **Auth:** Emergent Google OAuth + email/password JWT.
- **Billing:** Stripe subscriptions (3 core plans + Scribe add-on, 14-day free trial). Bundle coupon (`vetaura_scribe_bundle_20`, 20% off Scribe).
- **AI:** Claude Sonnet 5 (SOAP, differentials, discharge, receptionist) + OpenAI Whisper (audio transcription). Emergent Universal Key.
- **Voice + SMS:** Twilio Voice/SMS webhooks (voice/inbound → speech gather → Claude → TwiML reply; voicemail → Whisper → task; SMS → Claude → TwiML MessagingResponse). Per-clinic phone provisioning via IncomingPhoneNumbers.
- **Frontend:** React 19 + React Router + shadcn/ui + Tailwind + Recharts + Sonner.
- **Design:** Botanical Medical & Warm Precision — Forest greens (#236349), warm amber, sage canvas.

## Pricing (Feb 2026)
| Plan | Price | Voice minutes | Features |
| --- | --- | --- | --- |
| Starter | $249 / mo | Chat only | Inbox, Receptionist chat widget, 2 seats |
| Growth (most popular) | $499 / mo | 200 min | + Ambient Scribe, Template library, unlimited seats |
| Pro | $899 / mo | 800 min | + Phone & SMS routing, priority support |
| Scribe add-on | $79 / DVM / mo | — | Per-veterinarian ambient scribing |
| Overage | $0.35 / min | — | Auto-metered via Stripe |
| Bundle | 20% off Scribe when attached to any core plan at checkout |

## Implemented (v3 · Feb 2026)

### Marketing & sales
- Landing hero, feature grid, compliance strip
- **/pricing** — 3 core plans + Scribe add-on + bundle CTA
- **/features**, **/faq**, **/roi**, **/security**, **/how-it-works**, **/demo**
- **/try-it** — Public "Try it on your clinic" wizard: paste clinic URL → scrape → spin up ephemeral 24h demo receptionist with clinic hours/services/phone; live iframe chat + lead capture

### Auth & multi-tenant
- Email/password signup + login (JWT)
- Emergent Google OAuth
- Every doc scoped by `clinic_id`; verified 100% isolation between clinics

### Billing (Stripe)
- 4 products (Starter/Growth/Pro + Scribe add-on) with 14-day free trial
- `/api/payments/checkout` — single-plan checkout
- `/api/payments/checkout-bundle` — core plan + Scribe add-on in one session with 20% bundle coupon
- Billing portal + status polling + webhook

### Onboarding
- 3-step wizard: Clinic → Branding → Explore tips
- `onboarded` gate on ProtectedRoute
- Trial banner in sidebar

### Core clinical AI features
- Ambient SOAP scribe (mic + upload → Whisper → Claude → sign)
- **Scribe template library** — 5 built-in editable templates (wellness/dental/dermatology/euthanasia/post-op) + clinic-custom templates. Templates shape SOAP prompt with S/O/A/P hints and required-fields checklist.
- Differential diagnosis checklist
- Multilingual discharge (6 languages) + shareable owner portal
- Shift handoff summaries
- Patient records with weight/renal trends

### Client Inbox + Follow-up Copilot
- 7-category message classification
- AI-drafted replies (staff-reviewed)
- Deterministic emergency keyword safety net
- Auto-generated tasks: post-op check-ins, chronic monitoring, care gaps, stale-message
- Care & revenue gap dashboard

### AI Vet Receptionist
- Public website chat widget (`/r/{clinic_id}`)
- Configurable knowledge base, hours, pricing, rules
- **Phone & SMS routing (Twilio)** — per-clinic dedicated number, voice greeting → speech recognition → Claude reply, SMS threads, voicemail transcription via Whisper, emergency keyword override
- Voice usage metering per clinic + Stripe overage billing at $0.35/min

### Sellable extras
- Audit log for every AI draft/signature/share/approval
- CSV exports (`patients.csv`, `notes.csv`)
- Clinic branding (name, primary color, logo, footer)
- Public shareable owner portal (`/d/:token`)

## Files of reference
- `/app/backend/server.py` — routers, models, voice usage summary
- `/app/backend/ai_service.py` — Claude + Whisper prompts
- `/app/backend/stripe_service.py` — CATALOG, `ensure_catalog`, `checkout`, `checkout-bundle`, bundle coupon
- `/app/backend/scribe_templates.py` — Template CRUD, defaults, `template_prompt_block`
- `/app/backend/tryit_service.py` — URL scraping + ephemeral demo clinic
- `/app/backend/twilio_service.py` — voice/sms webhooks, number provisioning, usage logging
- `/app/backend/auth.py` — JWT + Emergent Google auth
- `/app/frontend/src/pages/marketing/TryIt.jsx` — public wizard
- `/app/frontend/src/pages/ScribeTemplates.jsx` — template library UI
- `/app/frontend/src/pages/PhoneSms.jsx` — Twilio settings + usage
- `/app/frontend/src/pages/AmbientScribe.jsx` — record + upload + template selector
- `/app/frontend/src/pages/Billing.jsx` — bundle toggle

## Testing
- Iteration 4: 19/19 backend tests + all frontend flows passing (`/app/backend/tests/test_iter4.py`)
- Iteration 2/3 tests still current (auth, isolation, billing, inbox)
- Test suite path: `/app/backend/tests/`

## Test credentials
See `/app/memory/test_credentials.md`. Stripe test card 4242 4242 4242 4242.

## Backlog (P0/P1/P2)
- **P1** Twilio credentials + PUBLIC_APP_URL wired for production phone provisioning (blocked on user creds)
- **P1** Stripe usage records auto-invoice for voice overage (currently metered; needs monthly billing job)
- **P1** Email delivery of discharge PDFs (Resend/SendGrid)
- **P1** Staff invitations (multi-user per clinic beyond owner)
- **P1** Real-time streaming transcript in ambient scribe (currently one-shot)
- **P2** Case studies / testimonials block on Landing
- **P2** Radiograph/x-ray upload + Claude vision triage
- **P2** Vaccine + preventive-care reminder automation (SMS via provisioned Twilio number)
- **P2** Owner-side account (view all discharges, refill requests, book appointments)
