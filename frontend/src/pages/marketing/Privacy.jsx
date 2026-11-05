import { Link } from "react-router-dom";
import MarketingShell from "@/components/MarketingShell";

const CONTENT = [
  {
    h: "1. What we collect",
    p: "Clinic account info (name, email, role), authentication data (hashed password or Google OAuth identifier), and clinical operational data your clinic chooses to enter (owner + patient records, appointment notes, transcripts, signed SOAP notes, discharge instructions, client messages, audit events, billing metadata). We do not collect pet-owner data directly — the clinic controls what owner information is entered.",
  },
  {
    h: "2. How we use it",
    p: "Solely to provide and operate the Vetaura service you signed up for: authentication, storing your clinical records, generating AI drafts on your behalf, processing subscription billing via Stripe, and logging activity in your audit trail.",
  },
  {
    h: "3. Sub-processors",
    p: "We use these sub-processors to run the service: Emergent (application hosting, database and AI gateway), Anthropic (Claude Opus 5.5 for clinical drafting), OpenAI (Whisper for audio transcription) and Stripe (subscription billing). Texting and email go through the Twilio and email accounts your clinic connects and controls. A current list is available on request. We do not sell your data or permit it to be used to train AI models.",
  },
  {
    h: "4. AI model training",
    p: "Your data is NEVER used to train the underlying AI models. Anthropic and OpenAI enterprise API endpoints run with zero-retention policies where available. Any transient copy held for the duration of a single request is discarded when the request completes.",
  },
  {
    h: "5. Encryption & security",
    p: "AES-256 at rest, TLS 1.3 in transit. Session tokens are HTTP-only, Secure, SameSite=None cookies with 7-day expiry. Audio recorded in the browser is streamed straight to transcription and never written to durable storage. Backups are encrypted and retained for 30 days.",
  },
  {
    h: "6. Data location & transfers",
    p: "Data is stored in the US. For international transfers we rely on Standard Contractual Clauses (SCCs). A Data Processing Addendum (DPA) is available on request.",
  },
  {
    h: "7. Retention & deletion",
    p: "Signed veterinary records are retained indefinitely unless you delete them, matching state/provincial veterinary medical record retention requirements. On written deletion request, we delete your clinic's records within 30 days from active systems and within 60 days from encrypted backups.",
  },
  {
    h: "8. Your rights",
    p: "You have the right to access, correct, export or delete your data at any time. EU/UK residents additionally have GDPR/UK-GDPR rights (data portability, objection to processing, complaint to a supervisory authority). California residents have CCPA/CPRA rights. Contact vetaura.app@gmail.com to exercise any right.",
  },
  {
    h: "9. Cookies",
    p: "We use strictly necessary cookies (session token). We do not use advertising or cross-site tracking cookies.",
  },
  {
    h: "10. Children",
    p: "Vetaura is not intended for use by children under 16. We do not knowingly collect data from children.",
  },
  {
    h: "11. Contact",
    p: "Privacy inquiries: vetaura.app@gmail.com · Security incidents: vetaura.app@gmail.com · Data requests: honored within 30 days (45 for CCPA).",
  },
];

export default function Privacy() {
  return (
    <MarketingShell>
      <section className="max-w-3xl mx-auto px-6 py-16">
        <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Legal</div>
        <h1 className="mt-2 font-serif-display text-4xl sm:text-5xl font-semibold text-emerald-950 tracking-tight">Privacy Policy</h1>
        <div className="text-xs text-slate-500 font-mono-clinical mt-2">Effective: {new Date().toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" })}</div>

        <div className="mt-10 space-y-6">
          {CONTENT.map((c) => (
            <div key={c.h}>
              <h2 className="font-serif-display text-xl font-semibold text-emerald-950 mb-1">{c.h}</h2>
              <p className="text-sm text-slate-700 leading-relaxed">{c.p}</p>
            </div>
          ))}
        </div>

        <div className="mt-12 text-sm text-slate-600">
          Questions? <a href="mailto:vetaura.app@gmail.com" className="text-emerald-800 hover:text-emerald-900 font-semibold">vetaura.app@gmail.com</a> · See also our <Link to="/legal/terms" className="text-emerald-800 hover:text-emerald-900 font-semibold">Terms of Service</Link> and <Link to="/security" className="text-emerald-800 hover:text-emerald-900 font-semibold">Security page</Link>.
        </div>
      </section>
    </MarketingShell>
  );
}
