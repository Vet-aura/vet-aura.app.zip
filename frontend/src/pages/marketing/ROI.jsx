import MarketingShell from "@/components/MarketingShell";
import RoiCalculator from "@/components/RoiCalculator";
import { Card } from "@/components/ui/card";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Clock, DollarSign, TrendingUp, Calendar, Users, ArrowRight } from "lucide-react";

const STATS = [
  {
    icon: Clock,
    big: "~2 hr / day",
    label: "documentation time reclaimed per DVM",
    body: "Independent studies of ambient AI scribes show a 50–80% reduction in charting time. Vetaura targets ~2 hours per clinician per day.",
    cite: "Published studies of ambient AI scribes (human medicine)",
  },
  {
    icon: DollarSign,
    big: "$5,600 / mo",
    label: "value recovered per DVM (est.)",
    body: "At an average $85/hr clinical value × 2 hr/day × 22 working days, one clinician recovers ~$5,610 per month in reclaimed hands-on time.",
    cite: "Illustrative estimate · adjust in the calculator",
  },
  {
    icon: TrendingUp,
    big: "+15–25%",
    label: "recheck & follow-through",
    body: "Clinic-branded owner portals with one-tap 'Request recheck' consistently lift follow-up compliance and reduce no-shows.",
    cite: "Industry estimate",
  },
  {
    icon: Calendar,
    big: "≤ 5 min",
    label: "from exam to signed SOAP",
    body: "Record, review, sign. Most clinicians finish the note before the patient walks out the door.",
    cite: "Vetaura internal target",
  },
];

const COST_PER_DVM = 399; // Growth plan monthly per location
const RECOVERED_PER_DVM = 5610;

const COMPARE = [
  { row: "Ambient SOAP scribe", vetaura: true, generic: false, manual: false },
  { row: "Species-aware differentials", vetaura: true, generic: false, manual: false },
  { row: "Multilingual owner discharges", vetaura: true, generic: false, manual: false },
  { row: "Clinic-branded owner portal + recheck CTA", vetaura: true, generic: false, manual: false },
  { row: "Shift handoff summaries", vetaura: true, generic: false, manual: false },
  { row: "Audit log & CSV export", vetaura: true, generic: "Partial", manual: false },
  { row: "Multi-tenant isolation", vetaura: true, generic: "Partial", manual: "N/A" },
  { row: "14-day free trial · no card", vetaura: true, generic: "Varies", manual: "N/A" },
];

export default function ROI() {
  return (
    <MarketingShell>
      {/* Hero */}
      <section className="max-w-6xl mx-auto px-6 pt-16 pb-12">
        <div className="text-center max-w-3xl mx-auto">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-50 border border-amber-200 text-amber-800 text-xs font-semibold uppercase tracking-wider">
            <TrendingUp className="h-3.5 w-3.5" /> The numbers
          </div>
          <h1 className="mt-5 font-serif-display text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight text-emerald-950 leading-[1.05]">
            Time back. Money back. Better care.
          </h1>
          <p className="mt-5 text-base sm:text-lg text-slate-600 leading-relaxed">
            Vetaura isn't a nice-to-have. Here's what a Growth-plan practice recovers in the first month.
          </p>
        </div>
      </section>

      {/* Big stat grid */}
      <section className="max-w-6xl mx-auto px-6 pb-10">
        <div className="grid md:grid-cols-2 gap-4">
          {STATS.map((s) => (
            <Card key={s.big} className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm" data-testid={`roi-stat-${s.big.replace(/\W+/g,'').toLowerCase()}`}>
              <div className="flex items-start justify-between">
                <div>
                  <div className="font-serif-display text-4xl sm:text-5xl font-semibold text-emerald-950">{s.big}</div>
                  <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold mt-1">{s.label}</div>
                </div>
                <div className="h-10 w-10 rounded-xl bg-emerald-50 border border-emerald-100 grid place-items-center text-emerald-700">
                  <s.icon className="h-5 w-5" />
                </div>
              </div>
              <div className="text-sm text-slate-600 leading-relaxed mt-4">{s.body}</div>
              <div className="text-[10px] font-mono-clinical text-slate-400 uppercase tracking-widest mt-3">{s.cite}</div>
            </Card>
          ))}
        </div>
      </section>

      {/* Interactive calculator */}
      <section className="max-w-6xl mx-auto px-6 pb-16">
        <RoiCalculator />
      </section>

      {/* Payback math */}
      <section className="bg-emerald-900 text-emerald-50">
        <div className="max-w-6xl mx-auto px-6 py-16 grid lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <div className="text-[10px] uppercase tracking-widest text-emerald-200/80 font-semibold">Payback in numbers</div>
            <h2 className="mt-2 font-serif-display text-3xl sm:text-4xl font-semibold text-white leading-tight">A 3-DVM clinic recovers &gt; $16,000 / month.</h2>
            <p className="mt-4 text-emerald-100/85 leading-relaxed">
              We're conservative on purpose. Even at half the industry benchmark, Vetaura pays for itself in the first week.
            </p>
            <div className="mt-6 grid sm:grid-cols-3 gap-3 text-sm">
              <div className="p-4 rounded-2xl bg-white/5 border border-white/10">
                <div className="text-[10px] uppercase tracking-widest text-emerald-200/80 font-semibold">Cost</div>
                <div className="mt-1 font-serif-display text-3xl font-semibold text-white">${COST_PER_DVM}</div>
                <div className="text-xs text-emerald-100/70">Growth plan · unlimited staff · per location</div>
              </div>
              <div className="p-4 rounded-2xl bg-white/5 border border-white/10">
                <div className="text-[10px] uppercase tracking-widest text-emerald-200/80 font-semibold">Recovered / DVM</div>
                <div className="mt-1 font-serif-display text-3xl font-semibold text-amber-300">${RECOVERED_PER_DVM.toLocaleString()}</div>
                <div className="text-xs text-emerald-100/70">Reclaimed clinical hours × avg. hourly value</div>
              </div>
              <div className="p-4 rounded-2xl bg-white/5 border border-white/10">
                <div className="text-[10px] uppercase tracking-widest text-emerald-200/80 font-semibold">3-DVM ROI</div>
                <div className="mt-1 font-serif-display text-3xl font-semibold text-white">{Math.round((RECOVERED_PER_DVM * 3) / COST_PER_DVM)}×</div>
                <div className="text-xs text-emerald-100/70">Return per dollar spent, first month</div>
              </div>
            </div>
            <div className="text-[10px] text-emerald-200/60 mt-4 font-mono-clinical">Ranges vary by caseload, staffing model and geography. Ask us for your clinic's projection.</div>
          </div>
          <div className="p-6 rounded-2xl bg-white/5 border border-white/10 self-center">
            <div className="text-[10px] uppercase tracking-widest text-emerald-200/80 font-semibold">Also recovered</div>
            <ul className="mt-3 space-y-2 text-sm">
              <li className="flex items-start gap-2"><Users className="h-4 w-4 text-amber-300 mt-0.5 flex-shrink-0" /> 20–30 min/day of front-desk time on client message triage</li>
              <li className="flex items-start gap-2"><Calendar className="h-4 w-4 text-amber-300 mt-0.5 flex-shrink-0" /> Fewer no-shows via one-tap recheck booking</li>
              <li className="flex items-start gap-2"><TrendingUp className="h-4 w-4 text-amber-300 mt-0.5 flex-shrink-0" /> Higher NPS from owners who actually understand the plan</li>
            </ul>
          </div>
        </div>
      </section>

      {/* Compare table */}
      <section className="max-w-6xl mx-auto px-6 py-16">
        <div className="max-w-2xl">
          <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Compared</div>
          <h2 className="mt-2 font-serif-display text-3xl sm:text-4xl font-semibold text-emerald-950 tracking-tight">Turn-key, not a duct-taped stack.</h2>
        </div>
        <Card className="mt-8 rounded-2xl border-emerald-100 bg-white shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[10px] uppercase tracking-widest text-slate-500 font-semibold border-b border-emerald-100 bg-emerald-50/50">
                  <th className="py-3 px-4">Capability</th>
                  <th className="py-3 px-4 text-center">Vetaura</th>
                  <th className="py-3 px-4 text-center">Generic AI note taker</th>
                  <th className="py-3 px-4 text-center">Paper + email</th>
                </tr>
              </thead>
              <tbody>
                {COMPARE.map((c, i) => (
                  <tr key={i} className="border-b border-emerald-50 last:border-0">
                    <td className="py-3 px-4 text-slate-800">{c.row}</td>
                    <td className={`py-3 px-4 text-center ${c.vetaura === true ? "text-emerald-700 font-semibold" : "text-slate-500"}`}>{c.vetaura === true ? "✓" : c.vetaura}</td>
                    <td className={`py-3 px-4 text-center text-slate-500`}>{c.generic === true ? "✓" : c.generic === false ? "—" : c.generic}</td>
                    <td className={`py-3 px-4 text-center text-slate-500`}>{c.manual === true ? "✓" : c.manual === false ? "—" : c.manual}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </section>

      {/* CTA */}
      <section className="max-w-6xl mx-auto px-6 pb-20 text-center">
        <h3 className="font-serif-display text-3xl font-semibold text-emerald-950">Ready to see it on your cases?</h3>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <Link to="/signup"><Button className="bg-emerald-700 hover:bg-emerald-800 text-white rounded-full h-11 px-6" data-testid="roi-start-trial">Start free trial <ArrowRight className="ml-2 h-4 w-4" /></Button></Link>
          <Link to="/demo"><Button variant="outline" className="rounded-full h-11 px-6 border-emerald-200 text-emerald-900 hover:bg-emerald-50" data-testid="roi-book-demo">Book a live demo</Button></Link>
        </div>
      </section>
    </MarketingShell>
  );
}
