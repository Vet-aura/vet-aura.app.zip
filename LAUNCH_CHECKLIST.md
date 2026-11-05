# Vetaura launch checklist

## Must do before taking real customers
- [ ] Production env vars set with strong random values: `JWT_SECRET`, `VETAURA_ADMIN_TOKEN`, `WEBHOOK_CRON_SECRET`, `VETAURA_ENCRYPTION_KEY` (none equal to test defaults)
- [ ] `PUBLIC_APP_URL=https://vet-aura.com` and `CORS_ORIGINS=https://vet-aura.com,https://www.vet-aura.com`
- [ ] Stripe account verified; live `STRIPE_SECRET_KEY` and a live webhook (`/api/payments/webhook`) with its `STRIPE_WEBHOOK_SECRET`
- [ ] vetaura.app@gmail.com is checked regularly (it is the public contact for support, privacy, security and legal)
- [ ] Lead alerts: `LEADS_NOTIFY_EMAIL`, `PLATFORM_RESEND_API_KEY`, `PLATFORM_FROM_EMAIL` (vet-aura.com verified in Resend)
- [ ] Terms and Privacy name the legal company and are reviewed by a lawyer (clinical AI + SMS)
- [ ] Emergent credit balance and auto top-up set: AI usage by clinics is billed to the Emergent LLM key
- [ ] Full end-to-end test on vet-aura.com (see below)

## End-to-end test (owner, vet, front desk; desktop and a 390px phone)
1. Sign up a new clinic, finish onboarding, see the 4 sample patients
2. Ambient scribe: load a sample transcript → SOAP draft → sign → note shows under the patient with the signer's real name
3. Differentials, Discharge (+ share link opens on a phone), Shift handoff, Client inbox draft → approve
4. Follow-ups auto-generate, Care gaps → draft outreach
5. Team: invite a vet and a front-desk user; confirm each role only sees what it should
6. Billing: Stripe checkout (test card in test mode), manage billing, trial banner
7. Marketing SMS with one owner: create template → blast → approve (confirm dialog)
8. Public pages on a phone: menu opens, Pricing, Try it, Book a demo (lead alert email arrives), Sign in
9. Phone layout: bottom bar + "More" reaches every screen, no sideways scrolling
