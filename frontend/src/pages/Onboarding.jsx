import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthProvider";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PawPrint, Check, ArrowRight, ArrowLeft, Sparkles } from "lucide-react";
import { toast } from "sonner";

const STEPS = ["Clinic", "Branding", "Explore"];

export default function Onboarding() {
  const { user, refreshUser } = useAuth();
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [form, setForm] = useState({
    name: user?.clinic?.name || "",
    primary_color: user?.clinic?.primary_color || "#236349",
    discharge_footer: "Meadow Ridge Veterinary · (415) 555-0100 · care@yourclinic.com",
  });
  const [busy, setBusy] = useState(false);

  async function saveAndNext() {
    setBusy(true);
    try {
      const patch = step === 0 ? { name: form.name } : { primary_color: form.primary_color, discharge_footer: form.discharge_footer };
      await api.patch("/clinic", patch);
      setStep((s) => s + 1);
    } catch {
      toast.error("Save failed.");
    } finally {
      setBusy(false);
    }
  }

  async function finish() {
    setBusy(true);
    try {
      await api.patch("/clinic", { onboarded: true });
      await refreshUser();
      toast.success("Your clinic is ready.");
      navigate("/app", { replace: true });
    } catch {
      toast.error("Save failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#f8f9f6] flex items-center justify-center p-6">
      <Card className="w-full max-w-2xl p-8 sm:p-10 rounded-2xl border-emerald-100 bg-white shadow-lg">
        <div className="flex items-center gap-2 mb-6">
          <div className="h-9 w-9 rounded-xl bg-emerald-700 grid place-items-center text-white"><PawPrint className="h-4 w-4" /></div>
          <span className="font-serif-display text-xl font-semibold text-emerald-950">Vetaura</span>
        </div>

        {/* progress */}
        <div className="flex items-center gap-2 mb-8">
          {STEPS.map((label, i) => (
            <div key={label} className="flex items-center gap-2 flex-1">
              <div className={`h-8 w-8 rounded-full grid place-items-center text-xs font-semibold ${i <= step ? "bg-emerald-700 text-white" : "bg-slate-100 text-slate-500"}`}>
                {i < step ? <Check className="h-4 w-4" /> : i + 1}
              </div>
              <div className={`text-sm font-medium ${i <= step ? "text-emerald-900" : "text-slate-400"}`}>{label}</div>
              {i < STEPS.length - 1 && <div className={`h-px flex-1 ${i < step ? "bg-emerald-300" : "bg-slate-200"}`} />}
            </div>
          ))}
        </div>

        {step === 0 && (
          <>
            <h1 className="font-serif-display text-3xl font-semibold text-emerald-950">Confirm your clinic.</h1>
            <p className="text-slate-600 mt-2 text-sm">This is what your staff and pet owners will see on notes and discharges.</p>
            <div className="mt-6 space-y-4">
              <div>
                <Label htmlFor="cn">Clinic name</Label>
                <Input id="cn" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="mt-1" data-testid="onboard-clinic-name" />
              </div>
              <div className="text-xs text-slate-500">We've pre-loaded 4 sample patients (Bella, Milo, Luna, Ollie) so you can test everything without adding real records first.</div>
            </div>
            <div className="flex justify-end mt-8">
              <Button onClick={saveAndNext} disabled={busy || !form.name} data-testid="onboard-next-1" className="bg-emerald-700 hover:bg-emerald-800 text-white rounded-full h-11 px-6">
                Continue <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </div>
          </>
        )}

        {step === 1 && (
          <>
            <h1 className="font-serif-display text-3xl font-semibold text-emerald-950">Make it yours.</h1>
            <p className="text-slate-600 mt-2 text-sm">Pick a brand color and a footer for owner-facing discharges.</p>
            <div className="mt-6 space-y-4">
              <div>
                <Label htmlFor="pc">Primary color</Label>
                <div className="mt-1 flex items-center gap-3">
                  <input type="color" value={form.primary_color} onChange={(e) => setForm({ ...form, primary_color: e.target.value })} className="h-10 w-14 rounded-lg border border-slate-200 cursor-pointer" data-testid="onboard-color" />
                  <Input value={form.primary_color} onChange={(e) => setForm({ ...form, primary_color: e.target.value })} className="font-mono-clinical" />
                </div>
              </div>
              <div>
                <Label htmlFor="df">Discharge footer</Label>
                <Input id="df" value={form.discharge_footer} onChange={(e) => setForm({ ...form, discharge_footer: e.target.value })} className="mt-1" data-testid="onboard-footer" />
                <div className="text-xs text-slate-500 mt-1">Appears at the bottom of every owner discharge portal.</div>
              </div>
            </div>
            <div className="flex justify-between mt-8">
              <Button variant="outline" onClick={() => setStep(0)} data-testid="onboard-back-1" className="rounded-full h-11 px-6"><ArrowLeft className="mr-2 h-4 w-4" /> Back</Button>
              <Button onClick={saveAndNext} disabled={busy} data-testid="onboard-next-2" className="bg-emerald-700 hover:bg-emerald-800 text-white rounded-full h-11 px-6">Continue <ArrowRight className="ml-2 h-4 w-4" /></Button>
            </div>
          </>
        )}

        {step === 2 && (
          <>
            <h1 className="font-serif-display text-3xl font-semibold text-emerald-950">You're set.</h1>
            <p className="text-slate-600 mt-2 text-sm">Try the Ambient Scribe first — it's the fastest way to feel the value.</p>
            <div className="mt-6 grid sm:grid-cols-2 gap-3">
              {[
                { title: "Record an appointment", body: "Or load a built-in sample transcript. Claude Opus 5.5 will draft a full SOAP.", tid: "onboard-tip-scribe" },
                { title: "Draft an owner discharge", body: "In Spanish, French, Mandarin — with a shareable owner-portal link.", tid: "onboard-tip-discharge" },
                { title: "Triage a client message", body: "Empathetic drafts with urgency tags; staff signs off.", tid: "onboard-tip-inbox" },
                { title: "Generate a shift handoff", body: "One click summarizes every hospitalized case.", tid: "onboard-tip-handoff" },
              ].map((t) => (
                <div key={t.title} className="p-4 rounded-xl border border-emerald-100 bg-emerald-50/40" data-testid={t.tid}>
                  <div className="font-semibold text-emerald-900 text-sm">{t.title}</div>
                  <div className="text-xs text-slate-600 mt-1">{t.body}</div>
                </div>
              ))}
            </div>
            <div className="flex justify-between mt-8">
              <Button variant="outline" onClick={() => setStep(1)} data-testid="onboard-back-2" className="rounded-full h-11 px-6"><ArrowLeft className="mr-2 h-4 w-4" /> Back</Button>
              <Button onClick={finish} disabled={busy} data-testid="onboard-finish" className="bg-emerald-700 hover:bg-emerald-800 text-white rounded-full h-11 px-6">Open the clinic <Sparkles className="ml-2 h-4 w-4" /></Button>
            </div>
          </>
        )}
      </Card>
    </div>
  );
}
