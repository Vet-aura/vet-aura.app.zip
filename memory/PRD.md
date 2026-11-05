# Vetaura — Clinical AI Copilot for Veterinary Practices

## Original problem statement
Veterinarian AI that helps veterinarians and staff for tedious jobs that take time away from the clients' animals during every appointment. **User asked to turn it into a sellable product** — multi-tenant SaaS with billing, marketing site, phone/SMS receptionist, ambient scribe, and Try-it-on-your-clinic public onboarding. In iteration 5 the user pivoted the Twilio + Email model to a **pure orchestrator / BYOK** design: each clinic owns their own Twilio account, A2P Brand + Campaign, consent records, and email provider. Vetaura orchestrates.

## Core principle
Vet-in-the-loop. Every AI output is a DRAFT. A clinician must review and sign before it affects care.

## Users
- Vet clinic owner — signs up, pays, invites staff, manages integrations & compliance
- Veterinarians (role: `vet`) — SOAP, differentials, discharges, inbox
- Vet techs (role: `tech`) — SOAP drafts, inbox, tasks, patients
- Front desk (role: `reception`) — inbox, tasks, receptionist config
- Pet owners — receive shareable branded discharge portal (no login) or email

## Architecture (Feb 2026 · v5 · BYOK + A2P compliance)
- **Backend:** FastAPI + Motor (Async MongoDB). Multi-tenant by `clinic_id` on every doc.
- **Auth:** Emergent Google OAuth + email/password JWT + role-based access control (owner/vet/tech/reception).
- **Billing:** Stripe subscriptions (3 core plans + Scribe add-on, 14-day trial). Bundle coupon (`vetaura_scribe_bundle_20`, 20% off Scribe). Metered price `vetaura_voice_overage_metered` for voice overage billing.
- **AI:** Claude Opus 5.5 (SOAP, differentials, discharge, receptionist) + OpenAI Whisper (audio + voicemail transcription). Emergent Universal Key.
- **Voice + SMS (per-clinic BYOK):** Clinic connects their OWN Twilio account via Restricted API Key (SID + Secret) + Messaging Service SID. Inbound webhooks are addressed by per-clinic tokenised URLs `/api/twilio/{voice,sms}/inbound/{clinic_id}/{webhook_token}`. Never accepts an Auth Token. Outbound provisioning and SMS via clinic's own credentials.
- **Email (per-clinic BYOK):** Clinic connects their OWN Resend or SendGrid API key + from-address. Every discharge email and team-invite email routes through the clinic's key.
- **A2P 10DLC:** Vetaura is a pure orchestrator — 11-item compliance checklist, Brand + Campaign attestation (clinic pastes their approved SIDs), consent ledger (immutable append-only events + materialised current status), STOP/HELP/START keyword handling, marketing vs care consent separation. No auto-generated legal text.
- **Secrets:** All BYOK secrets encrypted at rest with Fernet (`crypto_service.py`). Master key in `VETAURA_ENCRYPTION_KEY`.
- **Frontend:** React 19 + React Router + shadcn/ui + Tailwind + Recharts + Sonner.
- **Design:** Botanical Medical & Warm Precision — Forest greens (#236349), warm amber, sage canvas.

## Pricing (Feb 2026)
| Plan | Price | Voice minutes | Features |
| --- | --- | --- | --- |
| Starter | $249 / mo | Chat only | Inbox, Receptionist chat widget, 2 seats |
| Growth (most popular) | $499 / mo | 200 min | + Ambient Scribe, Template library, unlimited seats |
| Pro | $899 / mo | 800 min | + Phone & SMS routing, priority support |
| Scribe add-on | $79 / DVM / mo | — | Per-veterinarian ambient scribing |
| Voice overage | $0.35 / min | — | Auto-metered via Stripe usage records |
| Bundle | 20% off Scribe when attached to any core plan at checkout |

## Implemented (v5 · Feb 2026)

### Marketing & sales
- Landing hero, feature grid, compliance strip, Try-it CTA
- **/pricing** — 3 core plans + Scribe add-on + bundle CTA
- **/try-it** — Public "Try it on your clinic" wizard: paste URL → scrape → spin up ephemeral 24h demo receptionist
- **/roi**, **/security**, **/how-it-works**, **/faq**, **/features**, **/demo**

### Auth, teams & multi-tenant
- Email/password signup + Emergent Google OAuth
- **Staff invitations** (v5) — owner invites via email + role, 7-day token links, email delivery via clinic's BYOK provider with in-app copy-link fallback
- Roles: owner / vet / tech / reception with owner-only guardrails on invites, role changes, removals
- Every doc scoped by `clinic_id`

### Billing (Stripe)
- 4 products (Starter/Growth/Pro + Scribe) with 14-day trial
- `/api/payments/checkout` single-plan + `/api/payments/checkout-bundle` (20% Scribe bundle)
- **Voice-overage → Stripe metered usage records** (v5): `/api/billing-cycle/preview` (auth) shows the calling clinic's overage tally; `/api/billing-cycle/close` (X-Admin-Token) sweeps all clinics and pushes usage records. Idempotent per period.

### Onboarding
- 3-step wizard: Clinic → Branding → Explore tips
- `onboarded` gate on ProtectedRoute; trial banner in sidebar

### Core clinical AI features
- Ambient SOAP scribe (mic + upload → Whisper → Claude → sign)
- Scribe template library — 5 built-in editable templates + custom templates. Prompt-injected.
- Differential diagnosis checklist
- Multilingual discharge (6 languages) + shareable owner portal + **email-to-owner via clinic's own provider** (v5)
- Shift handoff summaries
- Patient records with weight/renal trends

### Client Inbox + Follow-up Copilot
- 7-category classification
- AI-drafted replies (staff-reviewed)
- Deterministic emergency keyword safety net
- Auto-generated tasks: post-op check-ins, chronic monitoring, care gaps, stale-message
- Care & revenue gap dashboard

### AI Vet Receptionist (chat + voice + SMS)
- Public website widget (`/r/{clinic_id}`), knowledge base config
- **Twilio Phone & SMS via clinic BYOK** (v5)
- STOP / HELP / START keyword auto-handling
- Consent ledger — immutable events + materialised status per (phone, consent_type)
- Marketing vs care consent isolation — marketing sends require SEPARATE explicit opt-in
- Voicemail → Whisper → Task workflow
- Emergency keyword deterministic bypass
- Voice usage metering per clinic + Stripe overage billing at $0.35/min

### Compliance (v5)
- 11-item A2P 10DLC compliance checklist per clinic
- Brand + Campaign SID attestation with status flags
- Business identity + opt-in disclosure fields captured for the clinic's records
- Consent-ledger UI — staff can record opt-ins manually and view full event history
- Amber warning banner: "Vetaura does not draft your legal text" (liability)

### Integrations page
- Twilio BYOK — Account SID + API Key SID + API Key Secret + Messaging Service SID; per-clinic webhook token displayed for pasting into Twilio Console
- Email BYOK — Resend or SendGrid; per-clinic from-email + from-name
- Both live-verified against provider APIs before persisting

### Sellable extras
- Audit log for every AI draft/signature/share/approval
- CSV exports
- Clinic branding (name, primary color, logo, footer)
- Public shareable owner portal (`/d/:token`)

## Files of reference (v5)
- Backend
  - `/app/backend/server.py` — routers, models, voice usage summary, discharge email endpoint
  - `/app/backend/auth.py` — JWT + Google auth + invite consumption at signup
  - `/app/backend/ai_service.py` — Claude + Whisper prompts
  - `/app/backend/stripe_service.py` — CATALOG, `ensure_catalog`, `checkout`, `checkout-bundle`
  - `/app/backend/scribe_templates.py` — Template CRUD, defaults, prompt injection
  - `/app/backend/tryit_service.py` — URL scraping + ephemeral demo clinic
  - `/app/backend/crypto_service.py` — Fernet encrypt/decrypt for BYOK secrets
  - `/app/backend/credentials_service.py` — Twilio + Email BYOK CRUD + live verification
  - `/app/backend/sms_compliance.py` — A2P checklist, consent ledger, STOP/HELP handling, `can_send_sms` gate
  - `/app/backend/twilio_service.py` — tokenised per-clinic webhooks, outbound send via Messaging Service
  - `/app/backend/email_service.py` — send_email abstraction (Resend/SendGrid)
  - `/app/backend/invitations.py` — staff invites + roles + public peek
  - `/app/backend/billing_cycle.py` — Stripe metered usage records for voice overage
- Frontend pages
  - `/app/frontend/src/pages/marketing/*.jsx` (Landing, Pricing, TryIt, ROI, Security, HowItWorks, FAQ, Features, Demo, Terms, Privacy)
  - `/app/frontend/src/pages/Integrations.jsx` — Twilio + Email BYOK
  - `/app/frontend/src/pages/SmsCompliance.jsx` — checklist + Brand/Campaign + consent ledger
  - `/app/frontend/src/pages/Team.jsx` — members + invitations
  - `/app/frontend/src/pages/PhoneSms.jsx` — number provisioning + usage
  - `/app/frontend/src/pages/ScribeTemplates.jsx` — template library
  - `/app/frontend/src/pages/AmbientScribe.jsx` — recording + template selector
  - `/app/frontend/src/pages/Discharge.jsx` — email-to-owner
  - `/app/frontend/src/pages/auth/InviteAccept.jsx` — invite signup

## Testing
- Iteration 5: 22/22 backend pytest passing (`/app/backend/tests/test_iter5.py`) + frontend flows verified
- Iterations 1–4 regression suites still passing
- Reports: `/app/test_reports/iteration_1.json` … `iteration_5.json`

## Test credentials
See `/app/memory/test_credentials.md`. Admin token: set `VETAURA_ADMIN_TOKEN` to a long random value in production (never the test default).

## 2026-06 — Quiet Hours, Login Rate Limiting, Marketing Bulk Blast (iteration 10, all passing)
- Quiet hours: clinic-set window + TZ + quiet days (Sunday default), owner-only edits; `sms_compliance.py` (`quiet_settings`, `_in_quiet_hours`, `next_send_window`); UI `components/QuietHoursCard.jsx` on /app/compliance. Marketing blocked, care unaffected.
- Brute-force protection: `login_security.py` LoginGuard — 5 fails/15 min per email -> 423 lockout 15 min; 20/15 min per IP -> 429 (login + signup). IP = 3rd-from-last XFF hop (anti-spoof). Audit `auth_audit`, alerts `security_alerts` (GET /api/security/alerts, ack, /auth-events — owner only) + owner email via clinic BYOK. UI `SecurityAlertsCard` in Settings.
- Marketing blast: `sms_campaigns.py` (/api/sms/marketing) — owner-only locked templates (merge fields first_name/pet_name/clinic_name), marketing-consent-only audience preview, pending_approval -> approval by a DIFFERENT owner -> send now or queue until quiet hours end. Per-recipient progress persisted; stale 'sending' recovered by cron. Page /app/marketing.
- Platform cron `.emergent/crons.yml` every 15 min -> POST /api/cron/sms-dispatch (Bearer WEBHOOK_CRON_SECRET).
- Note: preview pod egress alternates between 2 IPs, so per-IP tests can look flaky; per-email lockout is the primary guard.

## 2026-11 — Care reminders, blast tests/results, Twilio setup wizard, billing go-live (iterations 11–12)
- Care reminders (`care_reminders.py`, /app/reminders): care_items per patient (seeded), rules (offsets 14/0/-7, 10:00 local, skip quiet days), hourly cron /api/cron/care-reminders, sparse-unique dedupe_key, retry blocked/failed up to 3x, stale processing recovery.
- My mobile number with OTP (`phone_verify.py`), blast "Send test to my phone" (owner, verified mobile, 5/blast), blast Results sheet (reach, 7-day replies, opt-outs, 30-day bookings).
- Twilio setup wizard (`twilio_setup.py`, components/twilio-wizard/*): 7 guided steps (clinic does it themselves), read-only /check and /health, progress saved, webhook URLs. Integrations changes are owner-only.
- Billing: paywall (HTTP 402 via auth dep; trial/active/past_due 7-day grace), webhook sync for subscription.* / invoice.* / trial_will_end with event idempotency, owner-only checkout/portal, no double subscriptions, remaining trial carried over, safe redirect origins, StripeError -> 503, monthly overage cron.
- crypto_service no longer auto-generates VETAURA_ENCRYPTION_KEY (root cause of silent key rotation).
- Stripe managed sandbox key is EXPIRED in preview — user must claim sandbox (Preview → Manage → Payments) to take real payments.
- 2026-11-03: old sandbox unlinked; NEW claimable sandbox provisioned (acct_1UXmghB0mw23dZAJ, US, test). Tax mode "full" (Stripe manages tax). Real test checkout verified end-to-end (iteration_13). First deploy queued.
- AI model switched to Claude Opus 5.5 (ai_service.CLAUDE_MODEL = "claude-opus-5-5").


## Backlog (P0/P1/P2)
- **P1** Reminder automation: vaccine/preventive due dates -> automatic care SMS via clinic number
- **P1** Human-review path for urgent SMS conversations (already routes to Inbox as tasks)
- **P1** Scheduler for `billing-cycle/close` — currently requires external cron
- **P2** Case studies / testimonials on Landing
- **P2** Radiograph / X-ray upload with Claude vision triage
- **P2** Vaccine + preventive-care reminder automation (SMS via provisioned number)
- **P2** Owner-side account (view all discharges, refills, book appointments)
- **P2** ISV / Managed Communications tier (Twilio subaccount API workflow for done-for-you A2P onboarding)

## 2026-11 — Launch-readiness fixes (vet-aura.com)
- Mobile: app bottom bar now Dashboard / Inbox / Scribe / Patients / More; "More" opens a sheet with every screen. Marketing site has a mobile menu (incl. Sign in). Labs table scrolls on phones.
- Branding: page title, description, social preview tags and favicon set to Vetaura; contact emails use @vet-aura.com.
- Dashboard greeting uses the signed-in user's first name and time of day (was hard-coded "Good morning, Dr. Reyes").
- Marketing blasts: a clinic with a single owner can approve its own blast (with a confirm step); the two-person rule still applies when the clinic has 2+ owners.
- Leads: demo requests, Try-it demos and new clinic signups trigger an email alert (LEADS_NOTIFY_EMAIL + PLATFORM_RESEND_API_KEY + PLATFORM_FROM_EMAIL) and are listed at GET /api/admin/leads (X-Admin-Token).
- Security: backend refuses to start if JWT_SECRET is missing, "change-me" or shorter than 32 characters.
- Copy: removed claims the product does not support (end-to-end encryption, Workspace SSO/MFA control, VPC/KMS single-tenant deploys, SOC 2 in progress, 6-hourly backups, 99.9% uptime, EU-resident hosting, PIMS integration in onboarding), removed a made-up testimonial, fixed the bundle-discount wording, the "Clinic plan" name and outdated roadmap lines. Privacy policy now lists Emergent as host/AI gateway.
- Cost guard: public AI endpoints are rate-limited per visitor (receptionist chat 30 messages / 10 min per clinic; Try-it 5 demos / hour), stored in `public_rate_limits` with a TTL index (`public_rate_limit.py`).
