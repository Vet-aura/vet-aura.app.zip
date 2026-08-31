import { useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Sparkles, ClipboardList } from "lucide-react";
import { toast } from "sonner";

const TEMPLATES = [
  { label: "Chronic pruritus, canine", signalment: "5yo MN Labrador", complaint: "Chronic pruritus, non-seasonal, worse ventral abdomen and paws", findings: "Erythema ventral abdomen, interdigital pododermatitis, no external parasites seen on tape prep." },
  { label: "Feline weight loss", signalment: "13yo MN Domestic Shorthair", complaint: "Progressive weight loss over 3 months with normal appetite", findings: "BCS 3/9, palpable thyroid nodule on left, no abdominal masses, dehydration ~5%." },
  { label: "Acute vomiting dog", signalment: "3yo FS Boxer", complaint: "Acute vomiting for 24 hours, lethargic, decreased appetite", findings: "Mild abdominal discomfort, moderate dehydration, T 39.5, HR 130, MM tacky." },
];

const tierStyle = {
  Likely: "bg-emerald-100 text-emerald-800 border-emerald-200",
  Secondary: "bg-amber-100 text-amber-800 border-amber-200",
  "Rare-but-important": "bg-rose-100 text-rose-800 border-rose-200",
};

export default function Differentials() {
  const [signalment, setSignalment] = useState("");
  const [complaint, setComplaint] = useState("");
  const [findings, setFindings] = useState("");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  async function run() {
    if (!signalment || !complaint) return toast.info("Add at least signalment and complaint.");
    setBusy(true);
    try {
      const { data } = await api.post("/ai/differentials", { signalment, complaint, findings });
      setResult(data);
      toast.success("Differential checklist ready — review before use.");
    } catch {
      toast.error("Differential generation failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 lg:py-10 space-y-6">
      <div>
        <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Differentials</div>
        <h1 className="font-serif-display text-3xl sm:text-4xl font-semibold text-emerald-950 tracking-tight mt-1">Transparent decision support.</h1>
        <p className="text-sm text-slate-600 mt-2 max-w-2xl">A checklist to think through — not a diagnosis. Rank, rule-out and choose next diagnostics with the vet always in the loop.</p>
      </div>

      <div className="grid lg:grid-cols-12 gap-6">
        <div className="lg:col-span-5 space-y-3">
          <Card className="p-5 rounded-2xl border-emerald-100 bg-white shadow-sm space-y-3">
            <div>
              <div className="text-[10px] uppercase tracking-widest text-slate-500 font-semibold mb-1">Signalment</div>
              <Input value={signalment} onChange={(e) => setSignalment(e.target.value)} placeholder="e.g., 7yo SF Golden Retriever, 32kg" data-testid="diff-signalment" />
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-widest text-slate-500 font-semibold mb-1">Presenting complaint</div>
              <Textarea value={complaint} onChange={(e) => setComplaint(e.target.value)} placeholder="Chief complaint and history" rows={3} data-testid="diff-complaint" />
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-widest text-slate-500 font-semibold mb-1">Exam findings</div>
              <Textarea value={findings} onChange={(e) => setFindings(e.target.value)} placeholder="Vitals, physical exam, any prior work-up" rows={4} data-testid="diff-findings" />
            </div>
            <Button onClick={run} disabled={busy} data-testid="diff-generate" className="bg-emerald-700 hover:bg-emerald-800 text-white rounded-full w-full">
              <Sparkles className="h-4 w-4 mr-2" /> {busy ? "Thinking…" : "Generate differentials"}
            </Button>
          </Card>

          <Card className="p-5 rounded-2xl border-emerald-100 bg-white shadow-sm">
            <div className="text-xs uppercase tracking-widest text-slate-500 font-semibold mb-3">Templates</div>
            <div className="space-y-2">
              {TEMPLATES.map((t, i) => (
                <button
                  key={i}
                  onClick={() => { setSignalment(t.signalment); setComplaint(t.complaint); setFindings(t.findings); }}
                  data-testid={`diff-template-${i}`}
                  className="w-full text-left p-3 rounded-xl border border-slate-100 hover:border-emerald-300 hover:bg-emerald-50/40 transition-all"
                >
                  <div className="font-semibold text-sm text-slate-900">{t.label}</div>
                  <div className="text-xs text-slate-500">{t.signalment}</div>
                </button>
              ))}
            </div>
          </Card>
        </div>

        <div className="lg:col-span-7 space-y-4">
          {result ? (
            <>
              <Card className="p-5 rounded-2xl border-emerald-100 bg-white shadow-sm">
                <div className="text-xs uppercase tracking-widest text-slate-500 font-semibold mb-3">Differentials</div>
                <div className="space-y-2">
                  {(result.differentials || []).map((d, i) => (
                    <div key={i} className="p-3 rounded-xl border border-slate-100" data-testid={`diff-item-${i}`}>
                      <div className="flex items-center justify-between mb-1 gap-2 flex-wrap">
                        <div className="font-semibold text-slate-900">{d.name}</div>
                        <Badge className={`text-[10px] border ${tierStyle[d.tier] || "bg-slate-100 text-slate-700 border-slate-200"}`}>{d.tier}</Badge>
                      </div>
                      <div className="text-sm text-slate-600">{d.rationale}</div>
                      <div className="text-xs text-emerald-800 mt-2 font-medium">Next: {d.next_step}</div>
                    </div>
                  ))}
                </div>
              </Card>

              <div className="grid sm:grid-cols-2 gap-4">
                <Card className="p-5 rounded-2xl border-emerald-100 bg-white shadow-sm">
                  <div className="text-xs uppercase tracking-widest text-slate-500 font-semibold mb-2">Recommended workup</div>
                  <ul className="text-sm text-slate-700 space-y-1 list-disc list-inside">
                    {(result.recommended_workup || []).map((w, i) => <li key={i}>{w}</li>)}
                  </ul>
                </Card>
                <Card className="p-5 rounded-2xl border-emerald-100 bg-white shadow-sm">
                  <div className="text-xs uppercase tracking-widest text-slate-500 font-semibold mb-2">Questions for the owner</div>
                  <ul className="text-sm text-slate-700 space-y-1 list-disc list-inside">
                    {(result.questions_to_ask_owner || []).map((q, i) => <li key={i}>{q}</li>)}
                  </ul>
                </Card>
              </div>
              {(result.red_flags || []).length > 0 && (
                <Card className="p-5 rounded-2xl border-rose-200 bg-rose-50 shadow-sm">
                  <div className="text-xs uppercase tracking-widest text-rose-800 font-semibold mb-2">Red flags</div>
                  <ul className="text-sm text-rose-900 space-y-1 list-disc list-inside">
                    {result.red_flags.map((r, i) => <li key={i}>{r}</li>)}
                  </ul>
                </Card>
              )}
            </>
          ) : (
            <Card className="p-10 rounded-2xl border-emerald-100 bg-white shadow-sm text-center text-slate-500">
              <ClipboardList className="h-8 w-8 text-slate-300 mx-auto mb-2" /> Fill in the form (or load a template) to generate a differential checklist.
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
