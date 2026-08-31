import { Link } from "react-router-dom";
import MarketingShell from "@/components/MarketingShell";
import { Button } from "@/components/ui/button";
import { Mic, Stethoscope, ClipboardList, MessagesSquare, ArrowRight, ShieldCheck, Sparkles, Languages, FileCheck2, LineChart } from "lucide-react";

const FEATURES = [
  { icon: Mic, title: "Ambient SOAP scribe", body: "Record the exam — Vetaura drafts the S/O/A/P for you to review and sign in seconds." },
  { icon: ClipboardList, title: "Differential checklists", body: "Signalment + history in, transparent differentials, workup and questions out." },
  { icon: MessagesSquare, title: "Discharge & inbox", body: "Plain-language, multilingual pet-owner instructions and empathetic reply drafts." },
  { icon: Stethoscope, title: "Case handoffs", body: "One-click shift summaries with active problems, pending labs and next actions." },
  { icon: LineChart, title: "Longitudinal trends", body: "Watch weight, renal values, glucose and pain scores drift across every visit." },
  { icon: Languages, title: "Multilingual owners", body: "Send discharges in Spanish, French, German, Mandarin and Portuguese." },
  { icon: FileCheck2, title: "Audit-ready", body: "Every AI draft and signed note logged with clinician, timestamp and content." },
  { icon: ShieldCheck, title: "Vet-in-the-loop", body: "AI drafts only. Nothing enters the record until a clinician reviews and signs." },
];

export default function Landing() {
  return (
    <MarketingShell>
      {/* Hero */}
      <section className="max-w-7xl mx-auto px-6 pt-16 pb-20 grid lg:grid-cols-2 gap-10 items-center">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-50 border border-amber-200 text-amber-800 text-xs font-semibold uppercase tracking-wider">
            <Sparkles className="h-3.5 w-3.5" /> 14-day free trial · no card required
          </div>
          <h1 className="mt-5 font-serif-display text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight text-emerald-950 leading-[1.05]">
            Give every appointment back to the animal in the room.
          </h1>
          <p className="mt-5 text-base sm:text-lg text-slate-600 max-w-xl leading-relaxed">
            Vetaura listens through the visit, drafts your SOAP note, suggests differentials, writes the owner's discharge in plain language, and hands off the shift — while you keep both hands on the patient.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/signup" data-testid="landing-cta-signup">
              <Button className="bg-emerald-700 hover:bg-emerald-800 text-white rounded-full px-6 h-11">
                Start your free trial <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
            <Link to="/demo" data-testid="landing-cta-demo">
              <Button variant="outline" className="rounded-full px-6 h-11 border-emerald-200 hover:bg-emerald-50 text-emerald-900">Book a live demo</Button>
            </Link>
          </div>
          <div className="mt-10 flex items-center gap-6 text-xs text-slate-500">
            <div><span className="font-mono-clinical text-emerald-800 text-base font-semibold">~2 min</span><br />avg. note draft</div>
            <div className="h-8 w-px bg-emerald-100" />
            <div><span className="font-mono-clinical text-emerald-800 text-base font-semibold">S / O / A / P</span><br />structured &amp; editable</div>
            <div className="h-8 w-px bg-emerald-100" />
            <div><span className="font-mono-clinical text-emerald-800 text-base font-semibold">6 languages</span><br />owner instructions</div>
          </div>
        </div>

        <div className="relative">
          <div className="absolute -inset-3 rounded-3xl bg-emerald-100/40 blur-2xl" />
          <div className="relative rounded-3xl overflow-hidden border border-emerald-100 shadow-xl">
            <img
              src="https://images.unsplash.com/photo-1631980546596-a70e0d4c7cf7?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA2MDV8MHwxfHNlYXJjaHwzfHx2ZXRlcmluYXJpYW4lMjBleGFtaW5pbmclMjBnb2xkZW4lMjByZXRyaWV2ZXIlMjBkb2clMjBjbGluaWN8ZW58MHx8fHwxNzg4MTM0MTMyfDA&ixlib=rb-4.1.0&q=85"
              alt="Golden retriever with owner"
              className="w-full h-[520px] object-cover"
            />
            <div className="absolute left-4 right-4 bottom-4 rounded-2xl bg-white/95 backdrop-blur border border-emerald-100 p-4 shadow-lg">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-emerald-700">
                <span className="inline-flex h-2 w-2 rounded-full bg-rose-500 animate-pulse" /> Ambient recording · 04:12
              </div>
              <div className="mt-2 text-sm text-slate-700 leading-relaxed">
                <span className="font-semibold text-emerald-900">S:</span> Bella, 7yo SF Golden Retriever, presented for recheck of chronic otitis externa AU. Owner reports increased head shaking over the last 3 days…
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Feature grid */}
      <section className="max-w-7xl mx-auto px-6 pb-24">
        <div className="text-center max-w-2xl mx-auto mb-12">
          <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Every appointment</div>
          <h2 className="mt-2 font-serif-display text-3xl sm:text-4xl font-semibold text-emerald-950 tracking-tight">Built for the tedious parts, so you stay with the patient.</h2>
        </div>
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
          {FEATURES.map((f) => (
            <div key={f.title} className="p-6 rounded-2xl bg-white border border-emerald-100 hover:border-emerald-300 hover:shadow-md transition-all">
              <div className="h-10 w-10 rounded-xl bg-emerald-50 border border-emerald-100 grid place-items-center text-emerald-700 mb-4">
                <f.icon className="h-5 w-5" />
              </div>
              <div className="font-semibold text-slate-900 mb-1">{f.title}</div>
              <div className="text-sm text-slate-600 leading-relaxed">{f.body}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Compliance strip */}
      <section className="bg-emerald-900 text-emerald-50">
        <div className="max-w-7xl mx-auto px-6 py-16 grid md:grid-cols-3 gap-8">
          <div>
            <div className="text-[10px] uppercase tracking-widest text-emerald-200/80 font-semibold">Safe by design</div>
            <h3 className="mt-2 font-serif-display text-2xl font-semibold">Every output reviewed by a clinician.</h3>
            <p className="text-sm text-emerald-100/80 mt-3">Vetaura writes drafts. You sign what enters the record. Full audit log, per-user signatures, and clinic-branded exports.</p>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-widest text-emerald-200/80 font-semibold">Owner-friendly</div>
            <h3 className="mt-2 font-serif-display text-2xl font-semibold">Discharges owners actually read.</h3>
            <p className="text-sm text-emerald-100/80 mt-3">Share a mobile-friendly page with meds, warning signs and a one-tap recheck booking — translated into the owner's language.</p>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-widest text-emerald-200/80 font-semibold">Practice fit</div>
            <h3 className="mt-2 font-serif-display text-2xl font-semibold">Solo to multi-site.</h3>
            <p className="text-sm text-emerald-100/80 mt-3">Plans that scale with your caseload — with clinic-level branding, staff seats and shift handoffs.</p>
          </div>
        </div>
        <div className="max-w-7xl mx-auto px-6 pb-16 flex flex-wrap gap-3">
          <Link to="/pricing"><Button className="bg-white text-emerald-900 hover:bg-emerald-50 rounded-full px-6 h-11" data-testid="landing-view-pricing">View pricing <ArrowRight className="ml-2 h-4 w-4" /></Button></Link>
          <Link to="/signup"><Button variant="outline" className="rounded-full px-6 h-11 border-white/30 text-white bg-white/0 hover:bg-white/10" data-testid="landing-start-trial-bottom">Start free trial</Button></Link>
        </div>
      </section>
    </MarketingShell>
  );
}
