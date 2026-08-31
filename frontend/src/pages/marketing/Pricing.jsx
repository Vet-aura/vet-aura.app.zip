import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import MarketingShell from "@/components/MarketingShell";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Check, Sparkles } from "lucide-react";

const HIGHLIGHTS = {
  vetaura_solo_monthly: ["1 clinician seat", "Unlimited ambient scribe", "Differentials + discharge + inbox", "Multilingual owner portal", "Email support"],
  vetaura_clinic_monthly: ["Up to 8 staff seats", "Everything in Solo", "Shift handoff summaries", "Clinic branding", "Priority support"],
  vetaura_multisite_monthly: ["Unlimited seats & locations", "Everything in Clinic", "Per-site branding", "SSO & advanced audit log", "Dedicated success manager"],
};

export default function Pricing() {
  const [plans, setPlans] = useState([]);

  useEffect(() => {
    api.get("/plans").then((r) => setPlans(r.data.plans || [])).catch(() => {});
  }, []);

  return (
    <MarketingShell>
      <section className="max-w-6xl mx-auto px-6 py-16">
        <div className="text-center max-w-2xl mx-auto">
          <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Simple pricing</div>
          <h1 className="mt-2 font-serif-display text-4xl sm:text-5xl font-semibold text-emerald-950 tracking-tight">Every plan · 14-day free trial · cancel anytime.</h1>
          <p className="mt-4 text-slate-600">No card required to start. All plans include unlimited SOAP drafts, differentials, discharges and inbox triage.</p>
        </div>

        <div className="mt-12 grid md:grid-cols-3 gap-4">
          {plans.map((p, i) => {
            const highlighted = p.lookup_key === "vetaura_clinic_monthly";
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
                  <span className={`text-sm ${highlighted ? "text-emerald-200/80" : "text-slate-500"}`}>/mo</span>
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

        <div className="mt-16 text-center">
          <div className="text-xs text-slate-500">Need something custom for a hospital group?</div>
          <Link to="/demo" className="mt-2 inline-block font-semibold text-emerald-800 hover:text-emerald-900" data-testid="pricing-book-demo">Talk to us →</Link>
        </div>
      </section>
    </MarketingShell>
  );
}
