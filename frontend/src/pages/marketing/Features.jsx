import MarketingShell from "@/components/MarketingShell";
import { Card } from "@/components/ui/card";
import { Inbox as InboxIcon, ListTodo, TrendingUp, AlertOctagon, Mic, ClipboardList, MessagesSquare, Stethoscope, LineChart, Languages, FileCheck2, ShieldCheck, PawPrint, PhoneCall } from "lucide-react";

const HERO = {
  title: "Client Inbox + Follow-Up Copilot",
  body: "The flagship — because the fastest, safest way to help a busy clinic is to make sure no message and no medically important follow-up ever falls through the cracks.",
};

const FLAGSHIP = [
  {
    icon: InboxIcon,
    title: "Classified inbox — 7 buckets",
    body: "Every text, email or portal message auto-classified into: urgent review, appointment needed, refill request, lab follow-up, medication question, billing, or routine. One glance and staff know what's on fire and what can wait.",
  },
  {
    icon: AlertOctagon,
    title: "Belt-and-suspenders emergency triage",
    body: "Server-side detection of red-flag keywords (collapse, seizure, dyspnea, toxin, hit-by-car, bloat, uncontrolled bleeding, blocked cat) upgrades the message to urgent AND fires a high-priority task — even if the AI misses.",
  },
  {
    icon: ListTodo,
    title: "Auto-generated follow-up tasks",
    body: "Vetaura scans your patients on demand and creates tasks for post-op check-ins (Day 3/7/10), chronic monitoring windows, care alerts, and messages that have gone stale. Nothing depends on a staff member remembering.",
  },
  {
    icon: TrendingUp,
    title: "Care & revenue gap dashboard",
    body: "Every patient with an overdue vaccine, dental, heartworm test or chronic monitoring shows up in one screen. One click drafts an outreach task tied to that patient and owner.",
  },
  {
    icon: MessagesSquare,
    title: "Staff-reviewed AI drafts",
    body: "Empathetic, plain-language replies drafted by Claude Sonnet 5 with the pet's context loaded. Suggested follow-up task attached. Staff edits, approves, and sends — the audit log captures everything.",
  },
  {
    icon: ShieldCheck,
    title: "Track every loop closed",
    body: "One-click status pipeline per message: Sent → Awaiting reply → Booked → Paid → Closed. Never again lose track of who actually replied, booked, or picked up their meds.",
  },
];

const SUPPORTING = [
  { icon: PhoneCall, title: "AI Vet Receptionist", body: "24/7 website chat that answers hours, pricing, vaccines and booking questions from your approved info — hands off to a human the moment it can't answer or detects an emergency." },
  { icon: Mic, title: "Ambient SOAP scribe", body: "Record the exam — Whisper transcribes, Claude drafts a signed-ready SOAP note in seconds." },
  { icon: ClipboardList, title: "Differential checklists", body: "Signalment + history in, tiered differentials + workup + questions + red flags out." },
  { icon: Languages, title: "Multilingual owner discharges", body: "Plain-language, mobile-friendly discharge portal in 6 languages with a one-tap recheck button." },
  { icon: Stethoscope, title: "Shift handoff", body: "One click summarises every active patient into hospitalized cases, pending labs and next actions." },
  { icon: LineChart, title: "Longitudinal trends", body: "Weight, renal panel, glucose, seizure frequency charted across visits with reference-range highlights." },
  { icon: PawPrint, title: "Patient records", body: "Every owner, pet, visit, lab and appointment — searchable and scoped by clinic." },
  { icon: FileCheck2, title: "Audit log & CSV exports", body: "Every AI draft, every signature, every share logged. Export patients and notes as CSV any time." },
  { icon: ShieldCheck, title: "Vet-in-the-loop", body: "AI drafts only. Nothing enters the record until a licensed clinician reviews and signs." },
];

export default function Features() {
  return (
    <MarketingShell>
      <section className="max-w-6xl mx-auto px-6 pt-16 pb-8">
        <div className="text-center max-w-3xl mx-auto">
          <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">The flagship product</div>
          <h1 className="mt-2 font-serif-display text-4xl sm:text-5xl font-semibold text-emerald-950 tracking-tight">{HERO.title}</h1>
          <p className="mt-4 text-slate-600 leading-relaxed">{HERO.body}</p>
        </div>
      </section>

      <section className="max-w-6xl mx-auto px-6 pb-16">
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {FLAGSHIP.map((f) => (
            <Card key={f.title} className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm" data-testid={`feature-flagship-${f.title.split(" ")[0].toLowerCase()}`}>
              <div className="h-10 w-10 rounded-xl bg-emerald-50 border border-emerald-100 grid place-items-center text-emerald-700 mb-3">
                <f.icon className="h-5 w-5" />
              </div>
              <div className="font-serif-display text-lg font-semibold text-emerald-950 mb-1">{f.title}</div>
              <div className="text-sm text-slate-600 leading-relaxed">{f.body}</div>
            </Card>
          ))}
        </div>
      </section>

      <section className="bg-emerald-50/60 border-y border-emerald-100">
        <div className="max-w-6xl mx-auto px-6 py-16">
          <div className="max-w-2xl">
            <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Also included</div>
            <h2 className="mt-2 font-serif-display text-3xl sm:text-4xl font-semibold text-emerald-950 tracking-tight">Every tedious job in the appointment — handled.</h2>
          </div>
          <div className="mt-10 grid md:grid-cols-2 lg:grid-cols-4 gap-4">
            {SUPPORTING.map((f) => (
              <Card key={f.title} className="p-5 rounded-2xl border-emerald-100 bg-white shadow-sm">
                <div className="h-9 w-9 rounded-lg bg-emerald-50 border border-emerald-100 grid place-items-center text-emerald-700 mb-2">
                  <f.icon className="h-4 w-4" />
                </div>
                <div className="font-semibold text-emerald-950 text-sm">{f.title}</div>
                <div className="text-xs text-slate-600 mt-1 leading-relaxed">{f.body}</div>
              </Card>
            ))}
          </div>
        </div>
      </section>
    </MarketingShell>
  );
}
