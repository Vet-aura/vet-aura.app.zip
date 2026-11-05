import { Link } from "react-router-dom";
import MarketingShell from "@/components/MarketingShell";

const CONTENT = [
  {
    h: "1. Acceptance of terms",
    p: "By accessing Vetaura you agree to these Terms of Service. If you are using Vetaura on behalf of a clinic, you represent that you have authority to bind that clinic to these terms.",
  },
  {
    h: "2. Vet-in-the-loop principle",
    p: "Vetaura produces DRAFTS to assist licensed veterinarians. Vetaura does not diagnose, prescribe or treat. Every clinical output must be reviewed and signed by a licensed veterinarian before it enters the medical record or is delivered to a pet owner. You are solely responsible for clinical decisions.",
  },
  {
    h: "3. Your account & data",
    p: "You retain ownership of your clinical data. You grant Vetaura a limited license to process your data solely to provide the service. Your data is scoped to your clinic (multi-tenant isolation) and is never used to train the underlying AI models.",
  },
  {
    h: "4. Acceptable use",
    p: "You will not use Vetaura for human medical documentation, upload content that infringes third-party rights, attempt to reverse-engineer the service, or use the service to violate any law.",
  },
  {
    h: "5. Subscriptions & billing",
    p: "Vetaura is offered on monthly subscriptions with a 14-day free trial. Billing is handled by Stripe. You can cancel at any time from the in-app Billing screen. Refunds are considered case-by-case; no refunds for partial months.",
  },
  {
    h: "6. Availability",
    p: "We aim for high availability and announce scheduled maintenance in advance when we can. We are not liable for downtime caused by upstream providers (Anthropic, OpenAI, Stripe, cloud infrastructure).",
  },
  {
    h: "7. Termination",
    p: "You may cancel any time. We may suspend or terminate accounts that violate these terms or the law. Upon termination you have 30 days to export data before scheduled deletion.",
  },
  {
    h: "8. Warranties & liability",
    p: "The service is provided \"as is\". To the maximum extent permitted by law, Vetaura's aggregate liability is limited to fees paid in the 12 months preceding the claim. We disclaim liability for clinical outcomes — the licensed clinician remains responsible for all clinical decisions.",
  },
  {
    h: "9. Governing law",
    p: "These terms are governed by the laws of the State of Delaware, USA, without regard to conflict-of-laws principles. Disputes will be resolved in Delaware courts unless required otherwise by consumer-protection law in your jurisdiction.",
  },
  {
    h: "10. Changes",
    p: "We may update these terms. Material changes will be notified via email or in-app at least 30 days before taking effect.",
  },
];

export default function Terms() {
  return (
    <MarketingShell>
      <section className="max-w-3xl mx-auto px-6 py-16">
        <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Legal</div>
        <h1 className="mt-2 font-serif-display text-4xl sm:text-5xl font-semibold text-emerald-950 tracking-tight">Terms of Service</h1>
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
          Questions? <a href="mailto:vetaura.app@gmail.com" className="text-emerald-800 hover:text-emerald-900 font-semibold">vetaura.app@gmail.com</a> · See also our <Link to="/legal/privacy" className="text-emerald-800 hover:text-emerald-900 font-semibold">Privacy Policy</Link>.
        </div>
      </section>
    </MarketingShell>
  );
}
