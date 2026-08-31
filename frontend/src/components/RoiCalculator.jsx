import { useMemo, useState } from "react";
import { Card } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Link } from "react-router-dom";
import { Calculator, TrendingUp, Clock, DollarSign, PhoneCall, RotateCcw, ArrowRight, Sparkles } from "lucide-react";

// Sensible defaults for a small US general practice
const DEFAULTS = {
  dvms: 3,
  techs: 5,
  appts_per_dvm_per_day: 18,
  workdays_per_month: 22,
  note_minutes_baseline: 12,     // minutes per appointment (baseline)
  note_minutes_with_vetaura: 3,  // minutes per appointment with ambient scribe
  dvm_hourly_value: 120,         // $/hr — clinical value, not payroll
  tech_hourly_value: 45,
  missed_calls_per_day: 8,       // typical missed inbound calls
  capture_rate: 0.35,            // % of missed callers who convert once we answer/text back
  avg_appointment_value: 165,    // $ per completed appointment
  care_gap_recovered_per_month: 6,  // wellness/dental/derm cases per month surfaced by care-gap engine
  plan_price: 499,               // Growth plan
  attach_scribe: true,
  scribe_price_per_dvm: 79,
  bundle_discount: 0.20,         // 20% off scribe when bundled
};

const money = (n) => `$${Math.round(n).toLocaleString()}`;
const hoursMonthly = (mins) => (mins / 60).toFixed(1);

export default function RoiCalculator() {
  const [v, setV] = useState(DEFAULTS);
  const set = (k) => (val) => setV((prev) => ({ ...prev, [k]: Array.isArray(val) ? val[0] : val }));
  const setNumber = (k, min, max) => (e) => {
    const raw = Number(e.target?.value ?? e);
    if (Number.isNaN(raw)) return;
    setV((p) => ({ ...p, [k]: Math.max(min, Math.min(max, raw)) }));
  };

  const c = useMemo(() => {
    const total_appts_month = v.dvms * v.appts_per_dvm_per_day * v.workdays_per_month;
    // 1) Notes-time saved
    const minutes_saved_per_appt = Math.max(0, v.note_minutes_baseline - v.note_minutes_with_vetaura);
    const dvm_hours_saved = (minutes_saved_per_appt * total_appts_month) / 60;
    const dvm_hours_value = dvm_hours_saved * v.dvm_hourly_value;

    // 2) Tech time saved on inbox triage (avg 25 min / DVM / day of tech time freed)
    const tech_hours_saved = (25 / 60) * v.workdays_per_month * v.dvms;
    const tech_hours_value = tech_hours_saved * v.tech_hourly_value;

    // 3) Captured revenue from missed calls the AI receptionist answers
    const captured_appts = v.missed_calls_per_day * v.capture_rate * v.workdays_per_month;
    const captured_revenue = captured_appts * v.avg_appointment_value;

    // 4) Care-gap revenue (wellness/dental) auto-surfaced
    const care_gap_revenue = v.care_gap_recovered_per_month * v.avg_appointment_value * 1.6; // dental/derm avg ~1.6x

    // Costs
    const scribe_cost_raw = v.attach_scribe ? v.scribe_price_per_dvm * v.dvms : 0;
    const scribe_cost = scribe_cost_raw * (v.attach_scribe ? (1 - v.bundle_discount) : 1);
    const monthly_cost = v.plan_price + scribe_cost;

    const monthly_gain = dvm_hours_value + tech_hours_value + captured_revenue + care_gap_revenue;
    const monthly_net = monthly_gain - monthly_cost;
    const roi_multiple = monthly_cost > 0 ? monthly_gain / monthly_cost : 0;
    const payback_days = monthly_net > 0 ? Math.max(1, Math.round((monthly_cost / monthly_gain) * 30)) : null;

    return {
      total_appts_month,
      dvm_hours_saved, dvm_hours_value,
      tech_hours_saved, tech_hours_value,
      captured_appts, captured_revenue,
      care_gap_revenue,
      scribe_cost, monthly_cost,
      monthly_gain, monthly_net, roi_multiple, payback_days,
    };
  }, [v]);

  return (
    <Card className="p-6 sm:p-8 rounded-3xl border-emerald-100 bg-white shadow-sm relative overflow-hidden" data-testid="roi-calculator">
      <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-emerald-500 via-amber-400 to-emerald-600" />
      <div className="flex flex-wrap items-end justify-between gap-3 mb-6">
        <div>
          <div className="inline-flex items-center gap-2 text-[10px] uppercase tracking-widest text-emerald-700 font-semibold">
            <Calculator className="h-3.5 w-3.5" /> Live calculator
          </div>
          <h3 className="font-serif-display text-2xl sm:text-3xl font-semibold text-emerald-950 tracking-tight mt-1">Plug in your clinic. See the payback.</h3>
          <p className="text-sm text-slate-600 mt-1">All numbers below are yours. Tweak the sliders and watch the ROI move.</p>
        </div>
        <Button variant="outline" onClick={() => setV(DEFAULTS)} data-testid="roi-reset" className="rounded-full border-emerald-200 text-emerald-800 hover:bg-emerald-50 text-xs">
          <RotateCcw className="h-3 w-3 mr-1.5" /> Reset
        </Button>
      </div>

      <div className="grid lg:grid-cols-[1fr_1fr] gap-6">
        {/* Inputs */}
        <div className="space-y-5">
          <SliderRow label="Veterinarians (DVMs)" value={v.dvms} min={1} max={12} step={1} onChange={set("dvms")} display={v.dvms} tid="roi-dvms" />
          <SliderRow label="Vet techs" value={v.techs} min={0} max={20} step={1} onChange={set("techs")} display={v.techs} tid="roi-techs" />
          <SliderRow label="Appointments per DVM per day" value={v.appts_per_dvm_per_day} min={6} max={40} step={1} onChange={set("appts_per_dvm_per_day")} display={v.appts_per_dvm_per_day} tid="roi-appts" />
          <SliderRow label="Working days per month" value={v.workdays_per_month} min={16} max={26} step={1} onChange={set("workdays_per_month")} display={v.workdays_per_month} tid="roi-workdays" />
          <SliderRow label="Minutes on notes per appointment (today)" value={v.note_minutes_baseline} min={4} max={25} step={1} onChange={set("note_minutes_baseline")} display={`${v.note_minutes_baseline} min`} tid="roi-notes-baseline" />
          <SliderRow label="Minutes on notes per appointment (with Vetaura)" value={v.note_minutes_with_vetaura} min={1} max={10} step={1} onChange={set("note_minutes_with_vetaura")} display={`${v.note_minutes_with_vetaura} min`} tid="roi-notes-vetaura" />
          <SliderRow label="DVM effective hourly value" value={v.dvm_hourly_value} min={60} max={220} step={5} onChange={set("dvm_hourly_value")} display={`$${v.dvm_hourly_value}/hr`} tid="roi-dvm-rate" />
          <SliderRow label="Missed calls per day (before Vetaura)" value={v.missed_calls_per_day} min={0} max={30} step={1} onChange={set("missed_calls_per_day")} display={v.missed_calls_per_day} tid="roi-missed-calls" />
          <SliderRow label="Average appointment value" value={v.avg_appointment_value} min={60} max={400} step={5} onChange={set("avg_appointment_value")} display={money(v.avg_appointment_value)} tid="roi-appt-value" />

          <div className="pt-3 border-t border-emerald-100">
            <div className="text-[11px] uppercase tracking-widest text-emerald-700 font-semibold mb-2">Your Vetaura plan</div>
            <div className="grid grid-cols-2 gap-3">
              <label className="text-xs text-slate-600">Core plan / mo
                <Input type="number" min={0} max={5000} value={v.plan_price} onChange={setNumber("plan_price", 0, 5000)} data-testid="roi-plan-price" className="mt-1" />
              </label>
              <label className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer mt-4 sm:mt-6">
                <input type="checkbox" checked={v.attach_scribe} onChange={(e) => setV((p) => ({ ...p, attach_scribe: e.target.checked }))} data-testid="roi-attach-scribe" className="h-4 w-4 accent-emerald-700" />
                Attach Ambient Scribe · 20% bundle off
              </label>
            </div>
          </div>
        </div>

        {/* Outputs */}
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <StatBox tid="roi-out-net" tone="emerald" icon={TrendingUp} label="Net monthly recovery" value={money(c.monthly_net)} hint="After Vetaura cost" big />
            <StatBox tid="roi-out-roi" tone="amber" icon={Sparkles} label="ROI" value={c.roi_multiple >= 100 ? "∞" : `${c.roi_multiple.toFixed(1)}×`} hint={c.payback_days ? `Payback in ~${c.payback_days} days` : "Set inputs to see payback"} big />
          </div>
          <div className="grid grid-cols-1 gap-3">
            <BreakdownRow icon={Clock} label={`DVM time recovered (${c.dvm_hours_saved.toFixed(0)} hrs/mo across ${v.dvms} DVMs)`} value={money(c.dvm_hours_value)} tid="roi-out-dvm" />
            <BreakdownRow icon={Clock} label={`Tech time recovered (${c.tech_hours_saved.toFixed(0)} hrs/mo)`} value={money(c.tech_hours_value)} tid="roi-out-tech" />
            <BreakdownRow icon={PhoneCall} label={`Captured revenue from missed calls (${Math.round(c.captured_appts)} new appts/mo)`} value={money(c.captured_revenue)} tid="roi-out-captured" />
            <BreakdownRow icon={DollarSign} label={`Care-gap revenue surfaced by Vetaura`} value={money(c.care_gap_revenue)} tid="roi-out-caregap" />
            <div className="grid grid-cols-[1fr_auto] gap-2 items-center px-3 py-2.5 rounded-xl bg-slate-50 border border-slate-100 text-sm">
              <div className="text-slate-500">Vetaura cost this month</div>
              <div className="font-mono-clinical text-slate-700" data-testid="roi-out-cost">− {money(c.monthly_cost)}</div>
            </div>
            <div className="grid grid-cols-[1fr_auto] gap-2 items-center px-3 py-3 rounded-xl bg-emerald-900 text-emerald-50 border border-emerald-900 text-sm">
              <div className="text-emerald-100/80 uppercase tracking-widest text-[11px] font-semibold">Total monthly gain</div>
              <div className="font-serif-display text-2xl text-white" data-testid="roi-out-gain">{money(c.monthly_gain)}</div>
            </div>
          </div>

          <div className="pt-2 flex flex-col sm:flex-row gap-2">
            <Link to="/signup" className="flex-1">
              <Button className="w-full h-11 rounded-full bg-emerald-700 hover:bg-emerald-800 text-white" data-testid="roi-calc-cta-trial">
                Start free trial <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
            <Link to="/try-it" className="flex-1">
              <Button variant="outline" className="w-full h-11 rounded-full border-emerald-200 text-emerald-900 hover:bg-emerald-50" data-testid="roi-calc-cta-try">
                Try it on your clinic
              </Button>
            </Link>
          </div>
          <div className="text-[11px] text-slate-500 leading-relaxed">
            Assumptions: Ambient scribing reduces per-appt note time from your baseline to ~3 min. Tech time freed averages ~25 min/DVM/day from inbox triage automation. Care-gap revenue counts wellness/dental/derm cases the copilot surfaces per month (weighted 1.6× base appt value). Adjust any input to match your reality.
          </div>
        </div>
      </div>
    </Card>
  );
}

function SliderRow({ label, value, min, max, step, onChange, display, tid }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <label className="text-xs text-slate-600">{label}</label>
        <div className="text-sm font-mono-clinical text-emerald-900" data-testid={`${tid}-display`}>{display}</div>
      </div>
      <Slider value={[value]} min={min} max={max} step={step} onValueChange={onChange} data-testid={tid} className="mt-1" />
    </div>
  );
}

function StatBox({ label, value, hint, tone, icon: Icon, big, tid }) {
  const toneCls = tone === "amber"
    ? "bg-amber-50 border-amber-200 text-amber-900"
    : "bg-emerald-50 border-emerald-200 text-emerald-950";
  return (
    <div className={`p-4 rounded-2xl border ${toneCls}`} data-testid={tid}>
      <div className="flex items-center gap-2 mb-1">
        <Icon className={`h-4 w-4 ${tone === "amber" ? "text-amber-700" : "text-emerald-700"}`} />
        <div className="text-[10px] uppercase tracking-widest font-semibold opacity-80">{label}</div>
      </div>
      <div className={`font-serif-display ${big ? "text-3xl sm:text-4xl" : "text-2xl"} font-semibold`} data-testid={`${tid}-value`}>{value}</div>
      <div className="text-xs opacity-70 mt-0.5">{hint}</div>
    </div>
  );
}

function BreakdownRow({ label, value, icon: Icon, tid }) {
  return (
    <div className="grid grid-cols-[auto_1fr_auto] gap-3 items-center px-3 py-2.5 rounded-xl border border-emerald-100 bg-white">
      <Icon className="h-4 w-4 text-emerald-700" />
      <div className="text-sm text-slate-700">{label}</div>
      <div className="font-mono-clinical text-emerald-900 font-semibold" data-testid={tid}>+ {value}</div>
    </div>
  );
}
