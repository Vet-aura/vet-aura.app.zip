import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import MarketingShell from "@/components/MarketingShell";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Check, Sparkles, PhoneCall, Mic, Settings, ArrowRight, PawPrint } from "lucide-react";

const HIGHLIGHTS = {
  vetaura_starter_monthly: [
    "Client Inbox with 7-category classification",
    "AI-drafted message replies",
    "Follow-up task automation",
    "Care & revenue gap dashboard",
    "AI Receptionist website chat",
    "2 staff seats",
    "Email support",
  ],
  vetaura_growth_monthly: [
    "Everything in Starter",
    "Ambient SOAP Scribe (unlimited)",
    "Clinic-editable SOAP template library",
    "200 receptionist voice minutes / mo",
    "Multilingual owner discharge portal",
    "Audit log, CSV exports & branding",
    "Unlimited staff seats",
  ],
  vetaura_pro_monthly: [
    "Everything in Growth",
    "Phone & SMS receptionist routing",
    "Dedicated Twilio number per clinic",
    "800 receptionist voice minutes / mo",
    "After-hours voicemail → task workflow",
    "Priority support & onboarding",
  ],
};

const SCRIBE_KEY = "vetaura_scribe_addon_monthly";

export default function Pricing() {
  const [plans, setPlans] = useState([]);

  useEffect(() => {
    api.get("/plans").then((r) => setPlans(r.data.plans || [])).catch(() => {});
  }, []);

  const corePlans = plans.filter((p) => p.lookup_key !== SCRIBE_KEY);
  const scribe = plans.find((p) => p.lookup_key === SCRIBE_KEY);

  return (
    <MarketingShell>
      <section className="max-w-6xl mx-auto px-6 py-16">
        <div className="text-center max-w-2xl mx-auto">
          <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Simple, transparent pricing</div>
          <h1 className="mt-2 font-serif-display text-4xl sm:text-5xl font-semibold text-emerald-950 tracking-tight">Priced per clinic. 14-day free trial.</h1>
          <p className="mt-4 text-slate-600">No card required to start. Every plan includes multi-tenant data isolation, audit log, and vet-in-the-loop AI drafts.</p>
        </div>

        {/* Core plans */}
        <div className="mt-12 grid md:grid-cols-3 gap-4">
          {corePlans.map((p) => {
            const highlighted = p.lookup_key === "vetaura_growth_monthly";
            const bullets = HIGHLIGHTS[p.lookup_key] || [];
            return (
              <Card
                key={p.lookup_key}
                data-testid={`plan-${p.lookup_key}`}
                className={`p-8 rounded-2xl relative flex flex-col ${highlighted ? "bg-emerald-900 text-emerald-50 border-emerald-900 shadow-xl scale-105" : "bg-white border-emerald-100"}`}
              >
                {highlighted && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-amber-500 text-white text-[10px] font-semibold uppercase tracking-widest">Most popular</div>
                )}
                <div className={`text-xs uppercase tracking-widest font-semibold ${highlighted ? "text-emerald-200" : "text-emerald-700"}`}>Vetaura</div>
                <div className={`font-serif-display text-3xl font-semibold mt-1 ${highlighted ? "text-white" : "text-emerald-950"}`}>{p.product.replace("Vetaura ", "")}</div>
                <p className={`text-sm mt-1 mb-6 ${highlighted ? "text-emerald-100/80" : "text-slate-500"}`}>{p.description}</p>
                <div className="flex items-baseline gap-1">
                  <span className={`font-serif-display text-5xl font-semibold ${highlighted ? "text-white" : "text-emerald-950"}`}>${p.amount / 100}</span>
                  <span className={`text-sm ${highlighted ? "text-emerald-200/80" : "text-slate-500"}`}>/ location / mo</span>
                </div>
                <div className={`text-xs mt-1 ${highlighted ? "text-emerald-200/70" : "text-slate-400"}`}>
                  {p.trial_period_days ? `${p.trial_period_days}-day free trial` : ""}
                </div>
                <ul className="space-y-2 mt-6 flex-1">
                  {bullets.map((b, j) => (
                    <li key={j} className={`flex items-start gap-2 text-sm ${highlighted ? "text-emerald-50" : "text-slate-700"}`}>
                      <Check className={`h-4 w-4 mt-0.5 flex-shrink-0 ${highlighted ? "text-amber-300" : "text-emerald-600"}`} />
                      {b}
                    </li>
                  ))}
                </ul>
                <Link to="/signup" className="mt-8">
                  <Button
                    data-testid={`plan-cta-${p.lookup_key}`}
                    className={`w-full h-11 rounded-full ${highlighted ? "bg-white text-emerald-900 hover:bg-emerald-50" : "bg-emerald-700 hover:bg-emerald-800 text-white"}`}
                  >
                    Start free trial <Sparkles className="ml-2 h-4 w-4" />
                  </Button>
                </Link>
              </Card>
            );
          })}
        </div>

        {/* Multi-location + Add-ons + Setup */}
        <div className="mt-12 grid md:grid-cols-3 gap-4">
          {/* Multi-location */}
          <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm" data-testid="plan-multilocation">
            <div className="flex items-center gap-2 mb-2">
              <PawPrint className="h-4 w-4 text-emerald-700" />
              <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Multi-location</div>
            </div>
            <div className="font-serif-display text-2xl font-semibold text-emerald-950">Custom · ~$499–$599 / location / mo</div>
            <div className="text-sm text-slate-600 mt-2">For veterinary groups and hospital chains. Dedicated onboarding, volume discount and custom work scoped with you.</div>
            <Link to="/demo"><Button variant="outline" className="mt-4 rounded-full border-emerald-300 text-emerald-800 hover:bg-emerald-50" data-testid="plan-multilocation-cta">Talk to sales <ArrowRight className="ml-2 h-3 w-3" /></Button></Link>
          </Card>

          {/* Scribe add-on */}
          {scribe && (
            <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm" data-testid={`plan-${SCRIBE_KEY}`}>
              <div className="flex items-center gap-2 mb-2">
                <Mic className="h-4 w-4 text-emerald-700" />
                <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Ambient Scribe add-on</div>
              </div>
              <div className="font-serif-display text-2xl font-semibold text-emerald-950">${scribe.amount / 100} <span className="text-sm text-slate-500 font-sans">/ DVM / mo</span></div>
              <div className="text-sm text-slate-600 mt-2">Unlimited ambient SOAP scribing per veterinarian: record → Whisper → Claude drafts → sign. Editable template library included.</div>
              <div className="inline-flex items-center gap-1 mt-3 px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 text-[10px] uppercase tracking-widest font-semibold">Bundle 20% off</div>
              <div className="text-xs text-slate-400 mt-2 font-mono-clinical">Attach at checkout with any core plan.</div>
            </Card>
          )}

          {/* Onboarding / setup */}
          <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm" data-testid="plan-onboarding">
            <div className="flex items-center gap-2 mb-2">
              <Settings className="h-4 w-4 text-emerald-700" />
              <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">One-time onboarding</div>
            </div>
            <div className="font-serif-display text-2xl font-semibold text-emerald-950">$500 – $1,500</div>
            <div className="text-sm text-slate-600 mt-2">Workflow setup, clinic policy configuration, message templates, phone scripts, emergency-routing rules, and staff training. Multi-location implementations: $2,500 – $10,000+.</div>
          </Card>
        </div>

        {/* Voice overages */}
        <Card className="mt-8 p-6 rounded-2xl border-emerald-100 bg-emerald-50/40 shadow-sm" data-testid="plan-voice">
          <div className="flex items-center gap-2 mb-2">
            <PhoneCall className="h-4 w-4 text-emerald-700" />
            <div className="text-xs uppercase tracking-widest text-emerald-800 font-semibold">Voice AI allowance</div>
          </div>
          <div className="grid sm:grid-cols-4 gap-3 mt-3 text-sm">
            <div><span className="font-semibold text-slate-900">Starter:</span> <span className="text-slate-600">Chat only · no voice</span></div>
            <div><span className="font-semibold text-slate-900">Growth:</span> <span className="text-slate-600">200 min / mo</span></div>
            <div><span className="font-semibold text-slate-900">Pro:</span> <span className="text-slate-600">800 min / mo</span></div>
            <div><span className="font-semibold text-slate-900">Overage:</span> <span className="text-slate-600">$0.35 / min · auto-metered via Stripe</span></div>
          </div>
        </Card>

        {/* Launch offer */}
        <div className="mt-12 rounded-3xl bg-emerald-900 text-emerald-50 p-8 sm:p-10" data-testid="plan-launch-offer">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <div className="text-[10px] uppercase tracking-widest text-amber-300 font-semibold">Launch offer · first 10 clinics</div>
              <h3 className="mt-2 font-serif-display text-2xl sm:text-3xl font-semibold text-white">Growth for $349/mo · Scribe for $59/DVM · $500 setup.</h3>
              <p className="mt-2 text-emerald-100/85 text-sm max-w-2xl">Locked in for 12 months. Includes 250 receptionist voice minutes, template library, and priority onboarding. 60-day pilot, month-to-month cancellation. In exchange we ask for structured feedback and — if you're happy — a case study.</p>
            </div>
            <div className="flex gap-3">
              <Link to="/try-it"><Button variant="outline" className="border-white/40 text-white hover:bg-white/10 rounded-full h-11 px-6" data-testid="plan-try-cta">Try it on your clinic</Button></Link>
              <Link to="/demo"><Button className="bg-white text-emerald-900 hover:bg-emerald-50 rounded-full h-11 px-6" data-testid="plan-launch-cta">Claim the pilot <ArrowRight className="ml-2 h-4 w-4" /></Button></Link>
            </div>
          </div>
        </div>

        <div className="mt-14 text-center">
          <div className="text-xs text-slate-500 max-w-2xl mx-auto">
            Prices are per <span className="font-semibold text-slate-800">clinic location</span>. Multi-tenant data isolation, encryption in transit &amp; at rest, audit log, CSV exports, and vet-in-the-loop AI drafts are included on every plan.
          </div>
        </div>
      </section>
    </MarketingShell>
  );
}
