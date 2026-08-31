import { useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sparkles, Pill, AlertTriangle, MessagesSquare } from "lucide-react";
import { toast } from "sonner";

const LANGS = ["English", "Spanish", "French", "German", "Mandarin", "Portuguese"];

export default function Discharge() {
  const [petName, setPetName] = useState("Bella");
  const [plan, setPlan] = useState("Continue mometamax topical in both ears once daily for 10 more days. Ear cleaner (Epi-Otic) twice weekly. Bathe with chlorhexidine shampoo weekly. Recheck in 3 weeks for repeat ear cytology. Continue Apoquel 16mg once daily.");
  const [language, setLanguage] = useState("English");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  async function generate() {
    setBusy(true);
    try {
      const { data } = await api.post("/ai/discharge", { pet_name: petName, plan_notes: plan, language });
      setResult(data);
      toast.success("Discharge draft ready — review before sending to owner.");
    } catch {
      toast.error("Generation failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 lg:py-10 space-y-6">
      <div>
        <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Discharge instructions</div>
        <h1 className="font-serif-display text-3xl sm:text-4xl font-semibold text-emerald-950 tracking-tight mt-1">Plain-language, in the owner's language.</h1>
      </div>

      <div className="grid lg:grid-cols-12 gap-6">
        <Card className="lg:col-span-5 p-5 rounded-2xl border-emerald-100 bg-white shadow-sm space-y-3">
          <div>
            <div className="text-[10px] uppercase tracking-widest text-slate-500 font-semibold mb-1">Pet name</div>
            <Input value={petName} onChange={(e) => setPetName(e.target.value)} data-testid="disch-pet" />
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-widest text-slate-500 font-semibold mb-1">Language</div>
            <Select value={language} onValueChange={setLanguage}>
              <SelectTrigger data-testid="disch-lang"><SelectValue /></SelectTrigger>
              <SelectContent>
                {LANGS.map((l) => <SelectItem key={l} value={l}>{l}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-widest text-slate-500 font-semibold mb-1">Clinician-approved plan</div>
            <Textarea value={plan} onChange={(e) => setPlan(e.target.value)} rows={9} data-testid="disch-plan" />
          </div>
          <Button onClick={generate} disabled={busy} data-testid="disch-generate" className="bg-emerald-700 hover:bg-emerald-800 text-white rounded-full w-full">
            <Sparkles className="h-4 w-4 mr-2" /> {busy ? "Drafting…" : "Generate discharge"}
          </Button>
        </Card>

        <div className="lg:col-span-7 space-y-3">
          {result ? (
            <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm space-y-4">
              {result.greeting && <div className="text-slate-800">{result.greeting}</div>}
              {result.summary && (
                <div>
                  <div className="text-[10px] uppercase tracking-widest text-emerald-700 font-semibold mb-1">Today's visit</div>
                  <div className="text-sm text-slate-700 leading-relaxed">{result.summary}</div>
                </div>
              )}

              {(result.medications || []).length > 0 && (
                <div>
                  <div className="text-[10px] uppercase tracking-widest text-emerald-700 font-semibold mb-2 flex items-center gap-1"><Pill className="h-3 w-3" /> Medications</div>
                  <div className="grid sm:grid-cols-2 gap-2">
                    {result.medications.map((m, i) => (
                      <div key={i} className="p-3 rounded-xl border border-emerald-100 bg-emerald-50/40">
                        <div className="font-semibold text-emerald-900">{m.name}</div>
                        <div className="text-xs text-slate-600 font-mono-clinical">{m.dose} · {m.frequency}{m.duration ? ` · ${m.duration}` : ""}</div>
                        {m.notes && <div className="text-xs text-slate-600 mt-1">{m.notes}</div>}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {(result.home_care || []).length > 0 && (
                <div>
                  <div className="text-[10px] uppercase tracking-widest text-emerald-700 font-semibold mb-2">Home care</div>
                  <ul className="text-sm text-slate-700 space-y-1 list-disc list-inside">
                    {result.home_care.map((h, i) => <li key={i}>{h}</li>)}
                  </ul>
                </div>
              )}

              {(result.warning_signs || []).length > 0 && (
                <div className="p-4 rounded-xl bg-amber-50 border border-amber-200">
                  <div className="text-[10px] uppercase tracking-widest text-amber-800 font-semibold mb-2 flex items-center gap-1"><AlertTriangle className="h-3 w-3" /> Call the clinic immediately if…</div>
                  <ul className="text-sm text-amber-900 space-y-1 list-disc list-inside">
                    {result.warning_signs.map((w, i) => <li key={i}>{w}</li>)}
                  </ul>
                </div>
              )}

              {result.recheck && (
                <div>
                  <div className="text-[10px] uppercase tracking-widest text-emerald-700 font-semibold mb-1">Recheck</div>
                  <div className="text-sm text-slate-700">{result.recheck}</div>
                </div>
              )}
              {result.closing && <div className="text-sm text-slate-600 italic pt-2 border-t border-slate-100">{result.closing}</div>}
            </Card>
          ) : (
            <Card className="p-10 rounded-2xl border-emerald-100 bg-white text-center text-slate-500">
              <MessagesSquare className="h-8 w-8 text-slate-300 mx-auto mb-2" /> Draft plan on the left → generate discharge.
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
