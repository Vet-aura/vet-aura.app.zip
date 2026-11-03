import { AlertTriangle, CalendarClock } from "lucide-react";

const fmt = (iso) => (iso ? new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }) : null);

export function BillingNotices({ clinic }) {
  const blocked = clinic.billing_access === false;
  const items = [];
  if (blocked) {
    items.push(["paywall", "rose", clinic.plan_status === "past_due"
      ? "Your payment is more than 7 days overdue, so the app is paused. Update your card in Manage billing to pick up where you left off."
      : "Your free trial has ended or your subscription was canceled. Choose a plan below to unlock Vetaura again. Your data is safe."]);
  } else if (clinic.plan_status === "past_due") {
    items.push(["past-due", "amber", "Your last payment didn't go through. Update your card in Manage billing within 7 days to avoid losing access."]);
  }
  if (clinic.billing_notice && !blocked && clinic.plan_status !== "past_due") items.push(["notice", "amber", clinic.billing_notice]);
  const renew = fmt(clinic.current_period_end);

  return (
    <>
      {items.map(([k, tone, text]) => (
        <div key={k} data-testid={`billing-${k}`}
          className={tone === "rose" ? "flex gap-2 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900" : "flex gap-2 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900"}>
          <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" /> {text}
        </div>
      ))}
      {renew && clinic.stripe_subscription_id && (
        <div className="flex items-center gap-2 text-xs text-slate-600" data-testid="billing-renewal">
          <CalendarClock className="h-3.5 w-3.5" />
          {clinic.cancel_at_period_end ? `Cancels on ${renew}. You keep access until then.` : `${clinic.plan_status === "trialing" ? "First charge" : "Renews"} on ${renew}.`}
        </div>
      )}
    </>
  );
}
