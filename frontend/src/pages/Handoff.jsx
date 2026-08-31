import { useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Stethoscope, Sparkles } from "lucide-react";
import { toast } from "sonner";

const statusStyle = {
  stable: "bg-emerald-100 text-emerald-800 border-emerald-200",
  watch: "bg-amber-100 text-amber-800 border-amber-200",
  critical: "bg-rose-100 text-rose-800 border-rose-200",
};

export default function Handoff() {
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  async function generate() {
    setBusy(true);
    try {
      const { data } = await api.post("/ai/handoff", {});
      setResult(data);
      toast.success("Handoff summary drafted.");
    } catch {
      toast.error("Handoff generation failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 lg:py-10 space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
        <div>
          <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Shift handoff</div>
          <h1 className="font-serif-display text-3xl sm:text-4xl font-semibold text-emerald-950 tracking-tight mt-1">Every open case, one page.</h1>
        </div>
        <Button onClick={generate} disabled={busy} data-testid="handoff-generate" className="bg-emerald-700 hover:bg-emerald-800 text-white rounded-full h-11 px-5">
          <Sparkles className="h-4 w-4 mr-2" /> {busy ? "Drafting…" : "Generate handoff"}
        </Button>
      </div>

      {result ? (
        <div className="grid lg:grid-cols-3 gap-6">
          <Card className="lg:col-span-3 p-6 rounded-2xl border-emerald-100 bg-white shadow-sm">
            <div className="text-[10px] uppercase tracking-widest text-slate-500 font-semibold mb-2">Shift summary</div>
            <div className="text-slate-800 leading-relaxed">{result.shift_summary}</div>
          </Card>

          <Card className="lg:col-span-2 p-6 rounded-2xl border-emerald-100 bg-white shadow-sm">
            <div className="text-xs uppercase tracking-widest text-slate-500 font-semibold mb-3">Hospitalized patients</div>
            <div className="space-y-2">
              {(result.hospitalized_patients || []).map((p, i) => (
                <div key={i} className="p-3 rounded-xl border border-slate-100" data-testid={`handoff-pt-${i}`}>
                  <div className="flex items-center justify-between mb-1 flex-wrap gap-2">
                    <div className="font-semibold text-slate-900">{p.name}</div>
                    <Badge className={`text-[10px] border ${statusStyle[p.status] || "bg-slate-100 text-slate-700 border-slate-200"}`}>{p.status}</Badge>
                  </div>
                  <div className="text-sm text-slate-700">{p.problem}</div>
                  {p.pending && <div className="text-xs text-slate-500 mt-1">Pending: {p.pending}</div>}
                  {p.next_action && <div className="text-xs text-emerald-800 mt-1 font-medium">→ {p.next_action}</div>}
                </div>
              ))}
            </div>
          </Card>

          <div className="space-y-4">
            <Card className="p-5 rounded-2xl border-emerald-100 bg-white shadow-sm">
              <div className="text-xs uppercase tracking-widest text-slate-500 font-semibold mb-2">Pending labs</div>
              <ul className="text-sm text-slate-700 space-y-1 list-disc list-inside">
                {(result.pending_labs || []).map((l, i) => <li key={i}>{l}</li>)}
              </ul>
            </Card>
            <Card className="p-5 rounded-2xl border-emerald-100 bg-white shadow-sm">
              <div className="text-xs uppercase tracking-widest text-slate-500 font-semibold mb-2">Owner concerns</div>
              <ul className="text-sm text-slate-700 space-y-1 list-disc list-inside">
                {(result.owner_concerns || []).map((c, i) => <li key={i}>{c}</li>)}
              </ul>
            </Card>
            <Card className="p-5 rounded-2xl border-emerald-100 bg-white shadow-sm">
              <div className="text-xs uppercase tracking-widest text-slate-500 font-semibold mb-2">Priority tasks</div>
              <ul className="text-sm text-slate-700 space-y-1 list-disc list-inside">
                {(result.priority_tasks || []).map((t, i) => <li key={i}>{t}</li>)}
              </ul>
            </Card>
          </div>
        </div>
      ) : (
        <Card className="p-12 rounded-2xl border-emerald-100 bg-white shadow-sm text-center text-slate-500">
          <Stethoscope className="h-8 w-8 text-slate-300 mx-auto mb-2" /> Generate a handoff summary from all active patients.
        </Card>
      )}
    </div>
  );
}
