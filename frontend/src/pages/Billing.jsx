import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthProvider";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { CreditCard, Sparkles, Check, Loader2, Mic } from "lucide-react";
import { toast } from "sonner";

const HIGHLIGHTS = {
  vetaura_starter_monthly: ["Inbox + follow-ups", "2 staff seats", "Fair-use AI allowance"],
  vetaura_growth_monthly: ["Everything in Starter", "Unlimited staff", "Basic SOAP & discharge drafts", "Multilingual owner portal"],
  vetaura_pro_monthly: ["Everything in Growth", "AI Vet Receptionist", "1,000 voice min / mo", "Priority support"],
  vetaura_scribe_addon_monthly: ["Unlimited ambient SOAP scribing", "Per veterinarian add-on", "Species-specific vocab"],
};

const SCRIBE_KEY = "vetaura_scribe_addon_monthly";

export default function Billing() {
  const { user } = useAuth();
  const [plans, setPlans] = useState([]);
  const [busy, setBusy] = useState(null);

  useEffect(() => {
    api.get("/plans").then((r) => setPlans(r.data.plans || [])).catch(() => {});
  }, []);

  async function checkout(lookup_key) {
    setBusy(lookup_key);
    try {
      const { data } = await api.post("/payments/checkout", {
        lookup_key,
        origin_url: window.location.origin,
      });
      window.location.href = data.checkout_url;
    } catch {
      toast.error("Could not open checkout.");
      setBusy(null);
    }
  }

  async function portal() {
    try {
      const { data } = await api.post("/payments/portal", { origin_url: window.location.origin });
      window.location.href = data.portal_url;
    } catch {
      toast.error("Billing portal unavailable — subscribe first.");
    }
  }

  const clinic = user?.clinic || {};
  const trialLeft = clinic.trial_ends_at
    ? Math.max(0, Math.ceil((new Date(clinic.trial_ends_at) - new Date()) / 86400000))
    : 0;

  const corePlans = plans.filter((p) => p.lookup_key !== SCRIBE_KEY);
  const scribe = plans.find((p) => p.lookup_key === SCRIBE_KEY);

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6 lg:py-10 space-y-6">
      <div>
        <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Billing</div>
        <h1 className="font-serif-display text-3xl sm:text-4xl font-semibold text-emerald-950 tracking-tight mt-1">Your subscription.</h1>
      </div>

      <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm" data-testid="billing-status">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-xs uppercase tracking-widest text-slate-500 font-semibold">Current plan</div>
            <div className="mt-1 flex items-center gap-2 flex-wrap">
              <div className="font-serif-display text-2xl font-semibold text-emerald-950 capitalize">Vetaura {clinic.plan}</div>
              <Badge variant="outline" className="border-emerald-200 text-emerald-800 bg-emerald-50 capitalize">{clinic.plan_status || "trialing"}</Badge>
              {clinic.plan_status === "trialing" && trialLeft > 0 && (
                <Badge variant="outline" className="border-amber-200 text-amber-800 bg-amber-50">{trialLeft} days left in trial</Badge>
              )}
            </div>
          </div>
          {clinic.stripe_customer_id && (
            <Button onClick={portal} variant="outline" className="rounded-full border-emerald-300 text-emerald-800 hover:bg-emerald-50" data-testid="billing-portal">
              <CreditCard className="h-4 w-4 mr-2" /> Manage billing
            </Button>
          )}
        </div>
      </Card>

      <div className="grid md:grid-cols-3 gap-4">
        {corePlans.map((p) => {
          const highlighted = p.lookup_key === "vetaura_growth_monthly";
          const bullets = HIGHLIGHTS[p.lookup_key] || [];
          const current = clinic.plan && p.lookup_key.includes(clinic.plan);
          return (
            <Card key={p.lookup_key} className={`p-6 rounded-2xl relative flex flex-col ${highlighted ? "bg-emerald-900 text-emerald-50 border-emerald-900" : "bg-white border-emerald-100"}`} data-testid={`billing-plan-${p.lookup_key}`}>
              {highlighted && <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-amber-500 text-white text-[10px] font-semibold uppercase tracking-widest">Most popular</div>}
              <div className={`text-xs uppercase tracking-widest font-semibold ${highlighted ? "text-emerald-200" : "text-emerald-700"}`}>Vetaura</div>
              <div className={`font-serif-display text-2xl font-semibold mt-1 ${highlighted ? "text-white" : "text-emerald-950"}`}>{p.product.replace("Vetaura ", "")}</div>
              <div className="flex items-baseline gap-1 mt-3">
                <span className={`font-serif-display text-4xl font-semibold ${highlighted ? "text-white" : "text-emerald-950"}`}>${p.amount / 100}</span>
                <span className={`text-sm ${highlighted ? "text-emerald-200/80" : "text-slate-500"}`}>/ loc / mo</span>
              </div>
              <ul className="space-y-1.5 mt-5 flex-1">
                {bullets.map((b, i) => (
                  <li key={i} className={`flex items-start gap-2 text-sm ${highlighted ? "text-emerald-50" : "text-slate-700"}`}>
                    <Check className={`h-4 w-4 mt-0.5 flex-shrink-0 ${highlighted ? "text-amber-300" : "text-emerald-600"}`} /> {b}
                  </li>
                ))}
              </ul>
              <Button
                onClick={() => checkout(p.lookup_key)}
                disabled={busy === p.lookup_key}
                data-testid={`billing-cta-${p.lookup_key}`}
                className={`w-full h-11 rounded-full mt-6 ${highlighted ? "bg-white text-emerald-900 hover:bg-emerald-50" : "bg-emerald-700 hover:bg-emerald-800 text-white"}`}
              >
                {busy === p.lookup_key ? <Loader2 className="h-4 w-4 animate-spin" /> : (current ? "Current plan · manage" : (<>Subscribe <Sparkles className="ml-2 h-4 w-4" /></>))}
              </Button>
            </Card>
          );
        })}
      </div>

      {scribe && (
        <Card className="p-6 rounded-2xl border-emerald-100 bg-emerald-50/40 shadow-sm" data-testid={`billing-plan-${SCRIBE_KEY}`}>
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <Mic className="h-4 w-4 text-emerald-700" />
                <div className="text-xs uppercase tracking-widest text-emerald-800 font-semibold">Ambient Scribe · per DVM add-on</div>
              </div>
              <div className="font-serif-display text-2xl font-semibold text-emerald-950 mt-1">${scribe.amount / 100} <span className="text-sm text-slate-500 font-sans">/ DVM / month</span></div>
              <div className="text-sm text-slate-600 mt-1">Unlimited ambient SOAP scribing per veterinarian on top of any core plan.</div>
            </div>
            <Button
              onClick={() => checkout(SCRIBE_KEY)}
              disabled={busy === SCRIBE_KEY}
              data-testid={`billing-cta-${SCRIBE_KEY}`}
              className="bg-emerald-700 hover:bg-emerald-800 text-white rounded-full h-11 px-6"
            >
              {busy === SCRIBE_KEY ? <Loader2 className="h-4 w-4 animate-spin" /> : (<>Add per-DVM scribe <Sparkles className="ml-2 h-4 w-4" /></>)}
            </Button>
          </div>
        </Card>
      )}

      <div className="text-xs text-slate-500 text-center">Powered by Stripe · test card 4242 4242 4242 4242, any future expiry, any CVC. Prices are per <span className="font-semibold text-slate-800">clinic location</span>. Voice overage: $0.25/min beyond your plan allowance.</div>
    </div>
  );
}
