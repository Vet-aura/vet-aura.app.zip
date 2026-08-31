import { Link } from "react-router-dom";
import MarketingShell from "@/components/MarketingShell";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Mail, MessageSquare, PawPrint, Pill, AlertTriangle, CalendarPlus, ShieldCheck, Smartphone, ArrowRight, Check } from "lucide-react";

const STEPS = [
  {
    n: 1,
    icon: Mail,
    title: "You receive the link",
    body: "After the visit, your vet sends you a text or email with a Vetaura discharge link. No app to download. No password to remember.",
  },
  {
    n: 2,
    icon: Smartphone,
    title: "Open on your phone",
    body: "The page is clinic-branded and mobile-first. Read your pet's discharge instructions in your language — English, Spanish, French, German, Mandarin or Portuguese.",
  },
  {
    n: 3,
    icon: Pill,
    title: "See the meds — clearly",
    body: "Every medication with dose, schedule and 'give with food' notes. Warning signs highlighted so you know when to call.",
  },
  {
    n: 4,
    icon: CalendarPlus,
    title: "Tap to book the recheck",
    body: "One-tap request for your follow-up. The clinic calls or texts you back to confirm the time. Never lose track of the plan again.",
  },
];

const TRUST = [
  "Only you can see your pet's discharge — the link is private and unique",
  "No login, no password, no account needed",
  "Every instruction was reviewed and signed by your vet before you saw it",
  "Your data is encrypted and never sold, shared, or used to train AI",
  "Ask the clinic to delete the link at any time — deletion within 30 days",
];

export default function HowItWorks() {
  return (
    <MarketingShell>
      {/* Hero */}
      <section className="max-w-6xl mx-auto px-6 pt-16 pb-12">
        <div className="text-center max-w-3xl mx-auto">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-50 border border-amber-200 text-amber-800 text-xs font-semibold uppercase tracking-wider">
            <PawPrint className="h-3.5 w-3.5" /> For pet parents
          </div>
          <h1 className="mt-5 font-serif-display text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight text-emerald-950 leading-[1.05]">
            Your pet's care plan — right in your pocket.
          </h1>
          <p className="mt-5 text-base sm:text-lg text-slate-600 leading-relaxed">
            After every appointment, your Vetaura-enabled clinic can send you a private, mobile-friendly page with your pet's plan. Meds, warning signs, when to come back — all in plain language, in your language.
          </p>
        </div>
      </section>

      {/* Steps */}
      <section className="max-w-6xl mx-auto px-6 pb-16">
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
          {STEPS.map((s) => (
            <Card key={s.n} className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm relative" data-testid={`howto-step-${s.n}`}>
              <div className="absolute -top-3 -left-3 h-9 w-9 rounded-full bg-emerald-700 text-white grid place-items-center font-mono-clinical text-sm shadow-md">{s.n}</div>
              <div className="h-10 w-10 rounded-xl bg-emerald-50 border border-emerald-100 grid place-items-center text-emerald-700 mb-3 mt-2">
                <s.icon className="h-5 w-5" />
              </div>
              <div className="font-serif-display text-lg font-semibold text-emerald-950 mb-1">{s.title}</div>
              <div className="text-sm text-slate-600 leading-relaxed">{s.body}</div>
            </Card>
          ))}
        </div>
      </section>

      {/* Preview mock */}
      <section className="max-w-6xl mx-auto px-6 pb-16 grid lg:grid-cols-2 gap-10 items-center">
        <div>
          <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">A peek inside</div>
          <h2 className="mt-2 font-serif-display text-3xl sm:text-4xl font-semibold text-emerald-950 tracking-tight">Everything you need. Nothing you don't.</h2>
          <ul className="mt-6 space-y-2 text-sm text-slate-700">
            {[
              "Warm greeting from your veterinarian",
              "What happened today — in plain words, not jargon",
              "Every medication with a clear schedule",
              "Warning signs — 'Call the clinic immediately if…'",
              "When to come back for a recheck",
              "One-tap button to request the recheck",
            ].map((b, i) => (
              <li key={i} className="flex items-start gap-2"><Check className="h-4 w-4 text-emerald-600 mt-0.5" /> {b}</li>
            ))}
          </ul>
        </div>

        {/* Phone mock */}
        <div className="flex justify-center">
          <div className="w-[320px] rounded-[36px] bg-slate-900 p-3 shadow-2xl">
            <div className="rounded-[28px] overflow-hidden bg-[#f8f9f6]">
              <div className="bg-emerald-800 text-white px-5 py-5">
                <div className="flex items-center gap-2">
                  <div className="h-10 w-10 rounded-xl bg-white/15 grid place-items-center"><PawPrint className="h-5 w-5" /></div>
                  <div>
                    <div className="text-[9px] uppercase tracking-widest text-white/70 font-semibold">Discharge summary</div>
                    <div className="font-serif-display text-lg font-semibold">Meadow Ridge Vet</div>
                    <div className="text-[10px] text-white/80">For Bella · Signed by Dr. Reyes</div>
                  </div>
                </div>
              </div>
              <div className="p-4 space-y-3">
                <div className="text-xs text-slate-700 leading-relaxed">Hi Amelia — Bella had a great visit today. Her ear infection is looking a lot better…</div>
                <div className="rounded-xl bg-emerald-50 border border-emerald-100 p-3">
                  <div className="text-[9px] uppercase tracking-widest text-emerald-700 font-semibold flex items-center gap-1"><Pill className="h-3 w-3" /> Medications</div>
                  <div className="mt-1 text-xs font-semibold text-emerald-900">Mometamax drops</div>
                  <div className="text-[10px] font-mono-clinical text-slate-600">1 drop each ear · once daily · 10 days</div>
                </div>
                <div className="rounded-xl bg-amber-50 border border-amber-200 p-3">
                  <div className="text-[9px] uppercase tracking-widest text-amber-800 font-semibold flex items-center gap-1"><AlertTriangle className="h-3 w-3" /> Call immediately if…</div>
                  <div className="text-[10px] text-amber-900 mt-1">Bella becomes lethargic, stops eating, or the ear swells.</div>
                </div>
                <button className="w-full h-9 rounded-full bg-emerald-800 text-white text-xs font-semibold flex items-center justify-center gap-1"><CalendarPlus className="h-3 w-3" /> Request recheck appointment</button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Trust for owners */}
      <section className="bg-emerald-50/60 border-y border-emerald-100">
        <div className="max-w-6xl mx-auto px-6 py-16 grid lg:grid-cols-2 gap-10 items-center">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white border border-emerald-200 text-emerald-800 text-xs font-semibold uppercase tracking-wider">
              <ShieldCheck className="h-3.5 w-3.5" /> Safe for you and your pet
            </div>
            <h2 className="mt-3 font-serif-display text-3xl sm:text-4xl font-semibold text-emerald-950 tracking-tight">Safe. Private. Vet-approved.</h2>
            <p className="mt-3 text-slate-600 leading-relaxed">Vetaura only helps your veterinary team draft. Every word your vet sends you has been reviewed and signed by them personally.</p>
          </div>
          <ul className="space-y-2">
            {TRUST.map((t, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-slate-700 p-3 rounded-xl bg-white border border-emerald-100" data-testid={`howto-trust-${i}`}>
                <Check className="h-4 w-4 text-emerald-600 mt-0.5 flex-shrink-0" /> {t}
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* CTA back to vets */}
      <section className="max-w-6xl mx-auto px-6 py-16 text-center">
        <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Are you a veterinarian?</div>
        <h2 className="mt-2 font-serif-display text-3xl sm:text-4xl font-semibold text-emerald-950 tracking-tight">Give every appointment back to the animal in the room.</h2>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <Link to="/signup"><Button className="bg-emerald-700 hover:bg-emerald-800 text-white rounded-full h-11 px-6" data-testid="howto-start-trial">Start free trial <ArrowRight className="ml-2 h-4 w-4" /></Button></Link>
          <Link to="/demo"><Button variant="outline" className="rounded-full h-11 px-6 border-emerald-200 text-emerald-900 hover:bg-emerald-50">Book a live demo</Button></Link>
        </div>
      </section>
    </MarketingShell>
  );
}
