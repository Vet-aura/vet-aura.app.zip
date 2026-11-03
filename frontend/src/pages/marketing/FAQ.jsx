import MarketingShell from "@/components/MarketingShell";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";

const FAQS = [
  { q: "Is Vetaura making decisions for me?", a: "No. Vetaura writes DRAFTS — SOAP notes, discharge instructions, differential checklists and reply suggestions. Nothing enters the medical record or leaves the clinic without a clinician reviewing and signing. Confidence and flags are shown on every draft." },
  { q: "How safe is my clinic's data?", a: "Data is encrypted end-to-end (AES-256 at rest, TLS 1.3 in transit) and scoped by clinic_id at the query layer — two clinics on the same infrastructure never see each other's data. Session tokens are HTTP-only Secure cookies with 7-day expiry. Backups are encrypted and retained for 30 days. See our Security page for the full breakdown." },
  { q: "Where does the audio go?", a: "Audio is streamed to OpenAI Whisper for transcription and immediately discarded — never written to durable storage. Only the returned text transcript is kept in your clinic's private database (scoped by clinic_id), and only if you save the note." },
  { q: "Is my data used to train the AI?", a: "No. Your clinical data is NEVER used to train Anthropic's, OpenAI's or any other model. We run against enterprise API endpoints with zero-retention policies where available." },
  { q: "Does Vetaura run on my own server?", a: "Every Vetaura clinic gets its own isolated tenant environment — your data lives behind your MFA, your access policies, and (on the Multi-site plan) can be deployed to a dedicated single-tenant VPC with your own KMS keys and DNS. You bring the security perimeter; we plug into it." },
  { q: "Which AI models power Vetaura?", a: "Claude Opus 5.5 (Anthropic) for structured clinical drafting and OpenAI Whisper for speech-to-text. Every AI interaction is logged in your audit trail with user, action and timestamp." },
  { q: "What laws does Vetaura comply with?", a: "Vetaura follows the AVMA Model Veterinary Practice Act & VCPR framework (US), GDPR/UK-GDPR (EU/UK, DPA + SCCs available), CCPA/CPRA (California), state veterinary medical-record retention laws, and voluntarily follows HIPAA-parity controls even though veterinary records aren't covered by HIPAA. See our Security page." },
  { q: "Who owns the clinical records?", a: "You do. You retain full ownership of every note, transcript, lab and message. Vetaura only processes them to operate the service. One-click CSV export is always available, and written deletion requests are honored within 30 days (active systems) and 60 days (backups)." },
  { q: "Can I try before I buy?", a: "Yes — 14 days free, no card required. Sign up, get 4 seeded demo patients (Bella, Milo, Luna, Ollie), and try the ambient scribe on real recordings or a built-in sample transcript." },
  { q: "How is billing handled?", a: "Stripe subscriptions with a 14-day free trial. Upgrade, downgrade or cancel at any time from the in-app Billing screen. Invoices and receipts are emailed automatically. No refunds for partial months." },
  { q: "Which languages do owner discharges support?", a: "English, Spanish, French, German, Mandarin and Portuguese out of the box. The clinical plan you approve is preserved — Vetaura just re-writes it in the owner's language at a 6th-grade reading level." },
  { q: "Does Vetaura integrate with my PIMS?", a: "Today we support one-click CSV export and structured copy for pasting into eVetPractice, Cornerstone, AVImark and DVMax. Native integrations are on the 2026 roadmap — talk to us if you need one." },
  { q: "How do pet parents get their discharge?", a: "You click Draft & share; Vetaura mints a private, unguessable link that opens a clinic-branded, mobile-friendly page for the owner — with meds, warning signs and a one-tap recheck request. No account or password required." },
  { q: "What happens if I cancel?", a: "Your service continues until the end of the current billing cycle. You can export all data as CSV any time, including after cancellation. Deletion honored within 30 days on written request." },
  { q: "Do you have SOC 2 or a DPA?", a: "SOC 2 Type I preparation is in progress. A Data Processing Addendum (DPA) with Standard Contractual Clauses (SCCs) is available on request from security@vetaura.ai." },
  { q: "What if the AI is wrong?", a: "Every AI output is a draft only. Nothing is filed until a licensed clinician signs. Vetaura shows confidence and flags on every SOAP draft and every reply. The clinician remains responsible for all clinical decisions — Vetaura is a documentation and workflow copilot." },
];

export default function FAQ() {
  return (
    <MarketingShell>
      <section className="max-w-3xl mx-auto px-6 py-16">
        <div className="text-center">
          <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">FAQ</div>
          <h1 className="mt-2 font-serif-display text-4xl sm:text-5xl font-semibold text-emerald-950 tracking-tight">Answers.</h1>
        </div>

        <Accordion type="single" collapsible className="mt-10">
          {FAQS.map((f, i) => (
            <AccordionItem value={`item-${i}`} key={i} data-testid={`faq-${i}`}>
              <AccordionTrigger className="text-left font-semibold text-emerald-950 hover:text-emerald-800">{f.q}</AccordionTrigger>
              <AccordionContent className="text-slate-600 leading-relaxed">{f.a}</AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </section>
    </MarketingShell>
  );
}
