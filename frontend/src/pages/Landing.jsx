import { Link } from "react-router-dom";
import { PawPrint, Mic, Stethoscope, ClipboardList, MessagesSquare, ArrowRight, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";

const FEATURES = [
  { icon: Mic, title: "Ambient SOAP scribe", body: "Record the exam — Vetaura drafts the S/O/A/P for you to review and sign in seconds." },
  { icon: ClipboardList, title: "Differential checklists", body: "Signalment + history in, transparent differentials, workup and questions out." },
  { icon: MessagesSquare, title: "Discharge & inbox", body: "Plain-language, multilingual pet-owner instructions and empathetic reply drafts." },
  { icon: Stethoscope, title: "Case handoffs", body: "One-click shift summaries with active problems, pending labs and next actions." },
];

export default function Landing() {
  return (
    <div className="min-h-screen bg-[#f8f9f6] text-slate-800">
      {/* Top bar */}
      <header className="max-w-7xl mx-auto px-6 py-5 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2" data-testid="landing-brand">
          <div className="h-10 w-10 rounded-xl bg-emerald-700 grid place-items-center text-white shadow-sm">
            <PawPrint className="h-5 w-5" />
          </div>
          <div className="flex flex-col">
            <span className="font-serif-display text-xl font-semibold text-emerald-900 leading-none">Vetaura</span>
            <span className="text-[10px] uppercase tracking-widest text-emerald-700/70 mt-0.5">Clinical AI Copilot</span>
          </div>
        </Link>
        <Link to="/app" data-testid="landing-open-app">
          <Button className="bg-emerald-700 hover:bg-emerald-800 text-white rounded-full px-5">Open the clinic <ArrowRight className="ml-2 h-4 w-4" /></Button>
        </Link>
      </header>

      {/* Hero */}
      <section className="max-w-7xl mx-auto px-6 pt-8 pb-20 grid lg:grid-cols-2 gap-10 items-center">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-50 border border-amber-200 text-amber-800 text-xs font-semibold uppercase tracking-wider">
            <ShieldCheck className="h-3.5 w-3.5" /> Vet-in-the-loop by design
          </div>
          <h1 className="mt-5 font-serif-display text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight text-emerald-950 leading-[1.05]">
            Give every appointment back to the animal in the room.
          </h1>
          <p className="mt-5 text-base sm:text-lg text-slate-600 max-w-xl leading-relaxed">
            Vetaura listens through the visit, drafts your SOAP note, suggests differentials, writes the owner's discharge in plain language, and hands off the shift — while you keep both hands on the patient.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/app/scribe" data-testid="landing-try-scribe">
              <Button className="bg-emerald-700 hover:bg-emerald-800 text-white rounded-full px-6 h-11">
                Try the ambient scribe <Mic className="ml-2 h-4 w-4" />
              </Button>
            </Link>
            <Link to="/app" data-testid="landing-see-dashboard">
              <Button variant="outline" className="rounded-full px-6 h-11 border-emerald-200 hover:bg-emerald-50 text-emerald-900">See the clinic dashboard</Button>
            </Link>
          </div>
          <div className="mt-10 flex items-center gap-6 text-xs text-slate-500">
            <div><span className="font-mono-clinical text-emerald-800 text-base font-semibold">2 min</span><br />avg. note draft time</div>
            <div className="h-8 w-px bg-emerald-100" />
            <div><span className="font-mono-clinical text-emerald-800 text-base font-semibold">S / O / A / P</span><br />structured & editable</div>
            <div className="h-8 w-px bg-emerald-100" />
            <div><span className="font-mono-clinical text-emerald-800 text-base font-semibold">5+ languages</span><br />owner instructions</div>
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

      <footer className="max-w-7xl mx-auto px-6 py-10 border-t border-emerald-100 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-slate-500">
        <div>© {new Date().getFullYear()} Vetaura. Drafts only — clinician review required.</div>
        <div className="flex items-center gap-2 font-mono-clinical">Powered by Claude Sonnet 5 · OpenAI Whisper</div>
      </footer>
    </div>
  );
}
