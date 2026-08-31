import { Link } from "react-router-dom";
import MarketingShell from "@/components/MarketingShell";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Shield, Lock, Server, KeyRound, FileText, ScrollText, Eye, Trash2, ClipboardCheck, Globe2, ArrowRight, Check } from "lucide-react";

const PILLARS = [
  {
    icon: Lock,
    title: "Data encryption, everywhere",
    body: "AES-256 at rest for every note, transcript and lab. TLS 1.3 in transit. Encrypted database backups every 6 hours, retained for 30 days.",
  },
  {
    icon: Server,
    title: "Tenant isolation — your clinic, your silo",
    body: "Every record is scoped by clinic_id at the query layer, not just the UI. Two clinics on the same infrastructure can never see each other's data. Multi-site plan available with a dedicated tenant.",
  },
  {
    icon: KeyRound,
    title: "You control access",
    body: "Enforce your own MFA policy via Google Workspace SSO. Session tokens expire in 7 days. Instant staff revocation. Optional IP allow-list on Multi-site plan.",
  },
  {
    icon: ClipboardCheck,
    title: "Audit log — clinician-signed, timestamped",
    body: "Every AI draft, every signature, every share, every export, every message approval logged with user, action, target and metadata. Immutable append-only.",
  },
  {
    icon: Eye,
    title: "No training on your data",
    body: "Your transcripts, notes and messages are NEVER used to train the underlying AI models. Anthropic and OpenAI enterprise APIs run with zero-retention policies where available.",
  },
  {
    icon: Trash2,
    title: "You own it. Export or delete any time.",
    body: "One-click CSV export of patients and signed notes. Written deletion request honored within 30 days. Backups purged within 60 days of deletion.",
  },
];

const LEGAL = [
  {
    title: "Veterinary practice framework",
    body: "Vetaura is built as a documentation and workflow tool — it never issues a diagnosis, prescription or treatment plan on its own. Every clinical output is a draft the licensed veterinarian reviews and signs. This preserves the Veterinarian-Client-Patient Relationship (VCPR) required in every US state and equivalent frameworks in Canada, UK and EU.",
    cite: "AVMA Model Veterinary Practice Act · VCPR",
  },
  {
    title: "State medical record retention",
    body: "State laws require veterinary medical records to be retained 3–7 years after last patient visit. Vetaura retains signed notes indefinitely with 30-day rolling backups; you can export CSV at any time and delete on written request.",
    cite: "State-by-state VMR laws",
  },
  {
    title: "GDPR & UK GDPR (EU / UK clinics)",
    body: "For EU/UK clinics, Vetaura acts as a data processor under Art. 28. We provide a Data Processing Addendum (DPA), Standard Contractual Clauses (SCCs) for transfers, and a Record of Processing Activities (RoPA). Owner data may be handled under legitimate-interest or consent basis at the clinic's choice.",
    cite: "GDPR Art. 28 · UK GDPR",
  },
  {
    title: "CCPA / CPRA (California)",
    body: "California owners can request access, deletion or portability of their data. Vetaura provides tooling and honors requests within 45 days.",
    cite: "Cal. Civ. Code §1798.100",
  },
  {
    title: "HIPAA context",
    body: "Veterinary records are not covered by HIPAA (HIPAA applies to human protected health information). However, we voluntarily follow HIPAA-equivalent controls: audit logs, encryption at rest and in transit, least-privilege access and breach notification within 72 hours.",
    cite: "HIPAA · voluntary parity",
  },
  {
    title: "AI transparency & AVMA guidance",
    body: "Following AVMA guidance on AI in veterinary medicine (2024–2025), Vetaura discloses model provenance (Claude Sonnet 5, OpenAI Whisper), shows confidence and flags on every draft, keeps source transcripts for verification and requires clinician sign-off before anything enters the record.",
    cite: "AVMA AI in Veterinary Medicine guidance",
  },
  {
    title: "Owner consent language",
    body: "Vetaura provides a ready-to-adopt owner consent snippet you can add to intake paperwork disclosing that AI is used to assist documentation and communication — with clinician review — as recommended when AI materially contributes to clinical decision-making.",
    cite: "Recommended AVMA reporting practice",
  },
];

const CONTROLS = [
  "TLS 1.3 in transit · AES-256 at rest",
  "Role-based access (owner / vet / tech / front-desk)",
  "Immutable audit log · exportable",
  "Session-token expiry with instant revocation",
  "Automated encrypted backups every 6 hours (30-day retention)",
  "Vulnerability scanning · dependency alerting · patching SLA",
  "Breach notification within 72 hours of confirmed incident",
  "Optional dedicated tenant + VPC deploy (Multi-site plan)",
];

export default function Security() {
  return (
    <MarketingShell>
      {/* Hero */}
      <section className="max-w-6xl mx-auto px-6 pt-16 pb-12">
        <div className="text-center max-w-3xl mx-auto">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold uppercase tracking-wider">
            <Shield className="h-3.5 w-3.5" /> Security &amp; legal
          </div>
          <h1 className="mt-5 font-serif-display text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight text-emerald-950 leading-[1.05]">
            Your clinic's data. In your clinic's control.
          </h1>
          <p className="mt-5 text-base sm:text-lg text-slate-600 leading-relaxed">
            Vetaura is built for veterinarians who take patient records seriously. Encrypted end-to-end, siloed by clinic, audit-logged and exportable — with a vet-in-the-loop on every AI draft.
          </p>
        </div>
      </section>

      {/* Pillars */}
      <section className="max-w-6xl mx-auto px-6 pb-16">
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {PILLARS.map((p) => (
            <Card key={p.title} className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm" data-testid={`security-pillar-${p.title.split(" ")[0].toLowerCase()}`}>
              <div className="h-10 w-10 rounded-xl bg-emerald-50 border border-emerald-100 grid place-items-center text-emerald-700 mb-3">
                <p.icon className="h-5 w-5" />
              </div>
              <div className="font-serif-display text-xl font-semibold text-emerald-950 mb-1">{p.title}</div>
              <div className="text-sm text-slate-600 leading-relaxed">{p.body}</div>
            </Card>
          ))}
        </div>
      </section>

      {/* On your infrastructure */}
      <section className="bg-emerald-900 text-emerald-50">
        <div className="max-w-6xl mx-auto px-6 py-16 grid lg:grid-cols-2 gap-10 items-start">
          <div>
            <div className="text-[10px] uppercase tracking-widest text-emerald-200/80 font-semibold">Your infrastructure · your rules</div>
            <h2 className="mt-2 font-serif-display text-3xl sm:text-4xl font-semibold text-white leading-tight">
              Runs inside your world — behind your firewall, your MFA, your policies.
            </h2>
            <p className="mt-4 text-emerald-100/85 leading-relaxed">
              Every Vetaura clinic gets its own isolated tenant. Multi-site plans can request a <span className="text-white font-semibold">dedicated single-tenant deploy</span> inside a VPC — your DNS, your IAM, your KMS keys, your backup retention. You bring the security perimeter; we plug into it.
            </p>
            <ul className="mt-6 space-y-2">
              {CONTROLS.map((c, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-emerald-50">
                  <Check className="h-4 w-4 text-amber-300 mt-0.5 flex-shrink-0" /> {c}
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded-2xl bg-white/5 border border-white/10 backdrop-blur p-6">
            <div className="text-[10px] uppercase tracking-widest text-emerald-200/80 font-semibold">Data flow</div>
            <div className="mt-3 space-y-3 text-sm">
              {[
                { n: 1, t: "Clinician records or types", d: "Audio never touches disk. Streams direct to transcription." },
                { n: 2, t: "Whisper → text (discarded)", d: "Audio dropped once transcription is returned. Only text is stored, and only if you save the note." },
                { n: 3, t: "Claude drafts SOAP", d: "Draft is displayed in-browser. Zero-retention where the API supports it. Never used for training." },
                { n: 4, t: "Clinician reviews & signs", d: "Nothing enters the record until a licensed clinician signs. Signature + timestamp logged immutably." },
                { n: 5, t: "Optional share", d: "Owner portal link generated only if you click share. Owner sees no other patient's data." },
              ].map((s) => (
                <div key={s.n} className="flex items-start gap-3">
                  <div className="h-8 w-8 rounded-full bg-emerald-700 grid place-items-center text-white text-xs font-mono-clinical flex-shrink-0">{s.n}</div>
                  <div>
                    <div className="font-semibold text-white">{s.t}</div>
                    <div className="text-emerald-100/70 text-xs">{s.d}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Legal frameworks */}
      <section className="max-w-6xl mx-auto px-6 py-16">
        <div className="max-w-2xl">
          <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Legal channels &amp; frameworks</div>
          <h2 className="mt-2 font-serif-display text-3xl sm:text-4xl font-semibold text-emerald-950 tracking-tight">Every jurisdiction, addressed.</h2>
        </div>

        <div className="mt-10 grid lg:grid-cols-2 gap-4">
          {LEGAL.map((l) => (
            <Card key={l.title} className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm" data-testid={`legal-${l.title.split(" ")[0].toLowerCase()}`}>
              <div className="flex items-center gap-2">
                <ScrollText className="h-4 w-4 text-emerald-700" />
                <div className="font-semibold text-emerald-950">{l.title}</div>
              </div>
              <div className="text-sm text-slate-600 leading-relaxed mt-2">{l.body}</div>
              <div className="text-[10px] font-mono-clinical text-slate-400 mt-3 uppercase tracking-widest">{l.cite}</div>
            </Card>
          ))}
        </div>

        <div className="mt-10 flex flex-wrap gap-3 items-center text-sm">
          <Link to="/legal/terms" className="text-emerald-800 hover:text-emerald-900 font-semibold flex items-center gap-1" data-testid="link-terms"><FileText className="h-4 w-4" /> Terms of Service</Link>
          <span className="text-slate-300">·</span>
          <Link to="/legal/privacy" className="text-emerald-800 hover:text-emerald-900 font-semibold flex items-center gap-1" data-testid="link-privacy"><Lock className="h-4 w-4" /> Privacy Policy</Link>
          <span className="text-slate-300">·</span>
          <a href="mailto:security@vetaura.ai" className="text-emerald-800 hover:text-emerald-900 font-semibold flex items-center gap-1" data-testid="link-dpa"><Globe2 className="h-4 w-4" /> Request DPA / SCCs</a>
        </div>
      </section>

      {/* CTA */}
      <section className="max-w-6xl mx-auto px-6 pb-20">
        <Card className="p-8 rounded-2xl bg-white border-emerald-100 shadow-sm flex flex-col md:flex-row items-center justify-between gap-4">
          <div>
            <div className="font-serif-display text-2xl font-semibold text-emerald-950">Have a specific security question?</div>
            <div className="text-sm text-slate-600 mt-1">We answer within one business day and can share a full SOC 2 readiness statement, DPA and SCCs on request.</div>
          </div>
          <div className="flex gap-2">
            <Link to="/demo"><Button className="bg-emerald-700 hover:bg-emerald-800 text-white rounded-full h-11 px-5" data-testid="security-book-demo">Talk to us <ArrowRight className="ml-2 h-4 w-4" /></Button></Link>
            <Link to="/signup"><Button variant="outline" className="rounded-full h-11 px-5 border-emerald-200 text-emerald-900 hover:bg-emerald-50">Start free trial</Button></Link>
          </div>
        </Card>
      </section>
    </MarketingShell>
  );
}
