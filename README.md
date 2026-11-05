# Vetaura

AI copilot for veterinary clinics. Live at https://vet-aura.com.

- **Frontend:** React 19, React Router, Tailwind, shadcn/ui (`frontend/`)
- **Backend:** FastAPI + MongoDB (Motor) (`backend/`)
- **AI:** Claude Opus 5.5 (drafting) and OpenAI Whisper (transcription) via the Emergent LLM key
- **Billing:** Stripe subscriptions; **Texting/email:** each clinic connects its own Twilio and Resend/SendGrid
- **Hosting & scheduled jobs:** Emergent (`.emergent/crons.yml`)

Product spec and change history: `memory/PRD.md`. Pre-launch checklist: `LAUNCH_CHECKLIST.md`.

## Required environment variables (backend/.env, set in Emergent)

| Variable | Purpose |
| --- | --- |
| `MONGO_URL`, `DB_NAME` | Database |
| `JWT_SECRET` | Login token signing. Random, 32+ characters. The app will not start without it. |
| `VETAURA_ENCRYPTION_KEY` | Encrypts clinics' Twilio/email keys. Never change it once clinics have connected. |
| `WEBHOOK_CRON_SECRET` | Authenticates Emergent's scheduled jobs |
| `VETAURA_ADMIN_TOKEN` | Admin endpoints (`/api/admin/leads`, billing close). Random, long. |
| `EMERGENT_LLM_KEY` | AI calls (Claude + Whisper) |
| `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | Billing (use live keys in production) |
| `PUBLIC_APP_URL` | `https://vet-aura.com` |
| `CORS_ORIGINS` | `https://vet-aura.com,https://www.vet-aura.com` |
| `LEADS_NOTIFY_EMAIL`, `PLATFORM_RESEND_API_KEY`, `PLATFORM_FROM_EMAIL` | Optional: email alerts for demo requests, Try-it demos and new signups |
