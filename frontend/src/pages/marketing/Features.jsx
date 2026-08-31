import MarketingShell from "@/components/MarketingShell";
import { Card } from "@/components/ui/card";
import { Mic, ClipboardList, MessagesSquare, Stethoscope, LineChart, Languages, FileCheck2, ShieldCheck, PawPrint, Inbox } from "lucide-react";

const SECTIONS = [
  {
    icon: Mic,
    title: "Ambient scribe",
    body: "Record the exam in the room or upload after; OpenAI Whisper transcribes, Claude Sonnet 5 drafts a structured S/O/A/P note you review and sign. Every note is filed with the clinician's name and time-stamp.",
  },
  {
    icon: ClipboardList,
    title: "Differential diagnosis",
    body: "Type signalment, complaint and findings — Vetaura returns a transparent, tiered checklist (Likely / Secondary / Rare-but-important) with rationale, next diagnostic step, questions for the owner and red flags. Never a diagnosis on its own.",
  },
  {
    icon: MessagesSquare,
    title: "Multilingual discharge",
    body: "Turn any clinician-approved plan into a warm, plain-language owner letter in English, Spanish, French, German, Mandarin or Portuguese. Share it as a mobile-friendly branded portal link or export as text.",
  },
  {
    icon: Inbox,
    title: "Client inbox triage",
    body: "AI drafts empathetic replies with an urgency tag (urgent / routine / refill / post-op / scheduling). Every reply is reviewed by staff and logged in the audit trail.",
  },
  {
    icon: Stethoscope,
    title: "Shift handoff",
    body: "One click aggregates every active patient into hospitalized cases, pending labs, owner concerns and priority tasks — perfect for the incoming team.",
  },
  {
    icon: LineChart,
    title: "Longitudinal trends",
    body: "Weight, renal panel (Creatinine / SDMA / BUN / Phosphorus) and other markers charted across visits with reference-range highlighting.",
  },
  {
    icon: PawPrint,
    title: "Patient records & schedule",
    body: "Every owner, pet, visit and appointment in one place. Search, filter, alerts on overdue vaccines and pending rechecks.",
  },
  {
    icon: Languages,
    title: "Multilingual owner portal",
    body: "Owners receive a branded mobile page: meds with schedule, home care, warning signs, recheck info — with a one-tap 'Book recheck' button.",
  },
  {
    icon: FileCheck2,
    title: "Audit log & exports",
    body: "Every AI draft, every signed note, every message approval logged with user + timestamp. Download patient list and notes as CSV any time.",
  },
  {
    icon: ShieldCheck,
    title: "Vet-in-the-loop",
    body: "Vetaura never diagnoses, prescribes or files without clinician review. Confidence and flags surfaced on every draft; source transcripts kept for verification.",
  },
];

export default function Features() {
  return (
    <MarketingShell>
      <section className="max-w-6xl mx-auto px-6 py-16">
        <div className="text-center max-w-2xl mx-auto">
          <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Features</div>
          <h1 className="mt-2 font-serif-display text-4xl sm:text-5xl font-semibold text-emerald-950 tracking-tight">Every tedious job the appointment steals — handled.</h1>
        </div>

        <div className="mt-12 grid md:grid-cols-2 gap-4">
          {SECTIONS.map((s, i) => (
            <Card key={s.title} data-testid={`feature-${i}`} className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm">
              <div className="h-10 w-10 rounded-xl bg-emerald-50 border border-emerald-100 grid place-items-center text-emerald-700 mb-3">
                <s.icon className="h-5 w-5" />
              </div>
              <div className="font-serif-display text-xl font-semibold text-emerald-950 mb-1">{s.title}</div>
              <div className="text-sm text-slate-600 leading-relaxed">{s.body}</div>
            </Card>
          ))}
        </div>
      </section>
    </MarketingShell>
  );
}
