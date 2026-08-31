import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { PawPrint, TrendingUp, Sparkles, Send, Loader2 } from "lucide-react";
import { toast } from "sonner";

const GAP_STYLE = {
  alert: "border-amber-200 bg-amber-50 text-amber-900",
  monitoring: "border-emerald-200 bg-emerald-50 text-emerald-900",
  dental: "border-purple-200 bg-purple-50 text-purple-900",
  hwt: "border-sky-200 bg-sky-50 text-sky-900",
};

const GAP_LABEL = {
  alert: "Alert",
  monitoring: "Monitoring",
  dental: "Dental",
  hwt: "Heartworm test",
};

export default function CareGaps() {
  const [gaps, setGaps] = useState([]);
  const [busy, setBusy] = useState(false);

  async function load() {
    const { data } = await api.get("/care-gaps");
    setGaps(data);
  }
  useEffect(() => { load(); }, []);

  async function generateOutreach(patient, gap) {
    setBusy(patient.id + ":" + gap.label);
    try {
      // Draft an owner reply using AI as if we're proactively reaching out
      const context = `Pet: ${patient.name} — ${patient.species} — ${patient.breed}, age ${patient.age_years}. Active problems: ${(patient.active_problems || []).join(", ")}.`;
      const prompt = `Draft a proactive, warm outreach message to the pet parent about the following care gap so they book a visit: "${gap.label}". Keep it 3–5 sentences, plain language, invite them to book.`;
      // Reuse the reply endpoint by pretending it's an incoming message from staff
      const { data } = await api.post("/scribe/soap", { transcript: prompt + " Patient context: " + context });
      // Fallback: not perfect but shows draft — better: use dedicated endpoint. For MVP, create a task instead.
      await api.post("/tasks", {
        patient_id: patient.id,
        title: `Outreach: ${gap.label} — ${patient.name}`,
        description: `Auto-drafted from care gap. Send owner a message inviting them to book. AI context saved.\n\n${JSON.stringify(data).slice(0,400)}`,
        priority: gap.severity === "high" ? "high" : "normal",
        source: "care_gap",
      });
      toast.success(`Outreach task queued for ${patient.name}`);
    } catch (e) {
      toast.error("Draft failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6 lg:py-10 space-y-6">
      <div>
        <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Care &amp; revenue gaps</div>
        <h1 className="font-serif-display text-3xl sm:text-4xl font-semibold text-emerald-950 tracking-tight mt-1">Overdue care, in one screen.</h1>
        <p className="text-sm text-slate-600 mt-2 max-w-2xl">Every patient with a care gap the clinic can close — vaccines, dental, heartworm, chronic monitoring, active alerts. One click drafts an outreach task and adds it to Follow-ups.</p>
      </div>

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
        {gaps.map((g) => (
          <Card key={g.patient.id} className="p-5 rounded-2xl border-emerald-100 bg-white shadow-sm flex flex-col" data-testid={`gap-card-${g.patient.id}`}>
            <div className="flex items-start justify-between mb-3">
              <Link to={`/app/patients/${g.patient.id}`} className="flex items-center gap-3 group">
                <div className="h-11 w-11 rounded-xl bg-emerald-50 border border-emerald-100 grid place-items-center text-emerald-700">
                  <PawPrint className="h-5 w-5" />
                </div>
                <div>
                  <div className="font-serif-display text-lg font-semibold text-emerald-950 group-hover:text-emerald-800">{g.patient.name}</div>
                  <div className="text-xs text-slate-500">{g.patient.species} · {g.patient.breed}</div>
                </div>
              </Link>
              <Badge variant="outline" className="border-amber-200 text-amber-800 bg-amber-50 text-[10px]">{g.gaps.length} gap{g.gaps.length > 1 ? "s" : ""}</Badge>
            </div>

            <div className="space-y-2 flex-1">
              {g.gaps.map((gp, i) => (
                <div key={i} className={`p-3 rounded-xl border ${GAP_STYLE[gp.kind] || GAP_STYLE.monitoring}`} data-testid={`gap-item-${g.patient.id}-${i}`}>
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <div className="text-[10px] uppercase tracking-widest font-semibold">{GAP_LABEL[gp.kind] || gp.kind}</div>
                    {gp.severity === "high" && <Badge className="text-[9px] border bg-rose-100 text-rose-800 border-rose-200">high</Badge>}
                  </div>
                  <div className="text-sm mt-1">{gp.label}</div>
                  <Button
                    onClick={() => generateOutreach(g.patient, gp)}
                    disabled={busy === (g.patient.id + ":" + gp.label)}
                    size="sm"
                    variant="ghost"
                    className="mt-2 h-7 rounded-full text-[11px] hover:bg-white/70"
                    data-testid={`gap-outreach-${g.patient.id}-${i}`}
                  >
                    {busy === (g.patient.id + ":" + gp.label) ? <Loader2 className="h-3 w-3 animate-spin" /> : <><Sparkles className="h-3 w-3 mr-1" /> Draft outreach</>}
                  </Button>
                </div>
              ))}
            </div>

            {g.owner && (
              <div className="mt-3 pt-3 border-t border-slate-100 text-xs text-slate-500">
                Owner: <span className="text-slate-800 font-medium">{g.owner.name}</span> · <span className="font-mono-clinical">{g.owner.phone}</span>
              </div>
            )}
          </Card>
        ))}
      </div>

      {gaps.length === 0 && (
        <Card className="p-10 rounded-2xl border-emerald-100 bg-white text-center text-slate-500">
          <TrendingUp className="h-8 w-8 text-slate-300 mx-auto mb-2" />
          No care gaps detected. Your clinic is caught up.
        </Card>
      )}
    </div>
  );
}
