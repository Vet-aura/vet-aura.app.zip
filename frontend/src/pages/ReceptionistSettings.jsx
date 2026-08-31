import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthProvider";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { PhoneCall, Copy, ExternalLink, Plus, X, Check } from "lucide-react";
import { toast } from "sonner";

export default function ReceptionistSettings() {
  const { user } = useAuth();
  const [cfg, setCfg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    api.get("/receptionist/config").then((r) => setCfg(r.data));
  }, []);

  if (!cfg) return <div className="p-10 text-slate-500">Loading…</div>;

  const publicUrl = `${window.location.origin}/r/${user.clinic_id}`;

  function update(patch) { setCfg({ ...cfg, ...patch }); }

  async function save() {
    setBusy(true);
    try {
      const { data } = await api.patch("/receptionist/config", {
        enabled: cfg.enabled,
        hours_text: cfg.hours_text,
        address: cfg.address,
        emergency_phone: cfg.emergency_phone,
        emergency_instructions: cfg.emergency_instructions,
        species: cfg.species,
        appt_types: cfg.appt_types,
        pricing_text: cfg.pricing_text,
        vaccine_requirements: cfg.vaccine_requirements,
        medication_policy: cfg.medication_policy,
        new_client_policy: cfg.new_client_policy,
        deposit_policy: cfg.deposit_policy,
        faqs: cfg.faqs,
        greeting: cfg.greeting,
      });
      setCfg(data);
      toast.success("Receptionist settings saved.");
    } catch {
      toast.error("Save failed.");
    } finally {
      setBusy(false);
    }
  }

  async function copyLink() {
    await navigator.clipboard.writeText(publicUrl);
    setCopied(true);
    toast.success("Link copied — paste into your website chat button or SMS auto-reply.");
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-6 lg:py-10 space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
        <div>
          <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">AI Vet Receptionist</div>
          <h1 className="font-serif-display text-3xl sm:text-4xl font-semibold text-emerald-950 tracking-tight mt-1">Your after-hours front desk.</h1>
          <p className="text-sm text-slate-600 mt-2 max-w-2xl">Configure exactly what your AI Receptionist can say. It answers hours, pricing, vaccines and booking requests from your approved info — and hands off to your team the moment it hits its limits or detects an emergency.</p>
        </div>
        <div className="flex items-center gap-2">
          <Label htmlFor="enabled" className="text-xs font-semibold text-slate-600">Live</Label>
          <Switch id="enabled" checked={!!cfg.enabled} onCheckedChange={(v) => update({ enabled: v })} data-testid="recept-enabled" />
        </div>
      </div>

      {/* Share link */}
      <Card className="p-5 rounded-2xl border-emerald-100 bg-white shadow-sm" data-testid="recept-share-card">
        <div className="text-xs uppercase tracking-widest text-slate-500 font-semibold mb-2 flex items-center gap-1"><PhoneCall className="h-3 w-3" /> Your public receptionist link</div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="font-mono-clinical text-sm text-emerald-900 flex-1 min-w-0 truncate p-2 bg-emerald-50/60 rounded-lg border border-emerald-100">{publicUrl}</div>
          <Button onClick={copyLink} variant="outline" size="sm" data-testid="recept-copy" className="border-emerald-300 text-emerald-800 hover:bg-emerald-50 rounded-full">
            {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
          </Button>
          <a href={publicUrl} target="_blank" rel="noreferrer" data-testid="recept-open">
            <Button size="sm" className="bg-emerald-700 hover:bg-emerald-800 text-white rounded-full">Preview <ExternalLink className="ml-2 h-4 w-4" /></Button>
          </a>
        </div>
        <div className="text-xs text-slate-500 mt-2">Embed this link in your website chat button, Google Business profile, or SMS auto-reply. Phone / SMS integrations via Twilio are on the roadmap.</div>
      </Card>

      {/* Basics */}
      <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm space-y-4">
        <div className="text-xs uppercase tracking-widest text-slate-500 font-semibold">Clinic basics</div>
        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <Label>Hours</Label>
            <Input value={cfg.hours_text || ""} onChange={(e) => update({ hours_text: e.target.value })} data-testid="recept-hours" className="mt-1" />
          </div>
          <div>
            <Label>Address</Label>
            <Input value={cfg.address || ""} onChange={(e) => update({ address: e.target.value })} data-testid="recept-address" className="mt-1" />
          </div>
          <div>
            <Label>Emergency phone</Label>
            <Input value={cfg.emergency_phone || ""} onChange={(e) => update({ emergency_phone: e.target.value })} data-testid="recept-emg-phone" className="mt-1" />
          </div>
          <div>
            <Label>Greeting</Label>
            <Input value={cfg.greeting || ""} onChange={(e) => update({ greeting: e.target.value })} data-testid="recept-greeting" className="mt-1" />
          </div>
        </div>
        <div>
          <Label>Emergency instructions (shown when a red-flag keyword is detected)</Label>
          <Textarea rows={2} value={cfg.emergency_instructions || ""} onChange={(e) => update({ emergency_instructions: e.target.value })} data-testid="recept-emg-instr" className="mt-1" />
        </div>
      </Card>

      {/* Rules */}
      <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm space-y-4">
        <div className="text-xs uppercase tracking-widest text-slate-500 font-semibold">Booking rules</div>
        <ChipList label="Species accepted" value={cfg.species || []} onChange={(v) => update({ species: v })} testid="recept-species" />
        <ChipList label="Appointment types" value={cfg.appt_types || []} onChange={(v) => update({ appt_types: v })} testid="recept-appt-types" />
        <div>
          <Label>New-client policy</Label>
          <Textarea rows={2} value={cfg.new_client_policy || ""} onChange={(e) => update({ new_client_policy: e.target.value })} data-testid="recept-new-client" className="mt-1" />
        </div>
        <div>
          <Label>Deposit policy</Label>
          <Textarea rows={2} value={cfg.deposit_policy || ""} onChange={(e) => update({ deposit_policy: e.target.value })} data-testid="recept-deposit" className="mt-1" />
        </div>
      </Card>

      {/* Nonmedical info */}
      <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm space-y-4">
        <div className="text-xs uppercase tracking-widest text-slate-500 font-semibold">Approved non-medical info</div>
        <div>
          <Label>Pricing ranges</Label>
          <Textarea rows={2} value={cfg.pricing_text || ""} onChange={(e) => update({ pricing_text: e.target.value })} data-testid="recept-pricing" className="mt-1" />
        </div>
        <div>
          <Label>Vaccine requirements</Label>
          <Textarea rows={3} value={cfg.vaccine_requirements || ""} onChange={(e) => update({ vaccine_requirements: e.target.value })} data-testid="recept-vaccines" className="mt-1" />
        </div>
        <div>
          <Label>Medication pickup policy</Label>
          <Textarea rows={2} value={cfg.medication_policy || ""} onChange={(e) => update({ medication_policy: e.target.value })} data-testid="recept-meds" className="mt-1" />
        </div>
      </Card>

      {/* FAQs */}
      <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm space-y-3">
        <div className="flex items-center justify-between">
          <div className="text-xs uppercase tracking-widest text-slate-500 font-semibold">Approved FAQs</div>
          <Button size="sm" variant="outline" onClick={() => update({ faqs: [...(cfg.faqs || []), { q: "", a: "" }] })} data-testid="recept-faq-add" className="rounded-full border-emerald-300 text-emerald-800 hover:bg-emerald-50">
            <Plus className="h-3 w-3 mr-1" /> Add FAQ
          </Button>
        </div>
        {(cfg.faqs || []).map((f, i) => (
          <div key={i} className="p-3 rounded-xl border border-slate-100 space-y-2" data-testid={`recept-faq-${i}`}>
            <div className="flex items-center justify-between">
              <Badge variant="outline" className="text-[10px] border-emerald-200 text-emerald-800 bg-emerald-50">FAQ {i + 1}</Badge>
              <button onClick={() => update({ faqs: cfg.faqs.filter((_, j) => j !== i) })} className="text-slate-400 hover:text-rose-600" data-testid={`recept-faq-remove-${i}`}><X className="h-4 w-4" /></button>
            </div>
            <Input placeholder="Question" value={f.q} onChange={(e) => { const n = [...cfg.faqs]; n[i] = { ...n[i], q: e.target.value }; update({ faqs: n }); }} />
            <Textarea rows={2} placeholder="Answer" value={f.a} onChange={(e) => { const n = [...cfg.faqs]; n[i] = { ...n[i], a: e.target.value }; update({ faqs: n }); }} />
          </div>
        ))}
      </Card>

      <div className="flex justify-end">
        <Button onClick={save} disabled={busy} data-testid="recept-save" className="bg-emerald-700 hover:bg-emerald-800 text-white rounded-full h-11 px-6">
          {busy ? "Saving…" : "Save receptionist settings"}
        </Button>
      </div>
    </div>
  );
}

function ChipList({ label, value, onChange, testid }) {
  const [input, setInput] = useState("");
  function add() {
    const v = input.trim();
    if (!v) return;
    if (!value.includes(v)) onChange([...value, v]);
    setInput("");
  }
  return (
    <div>
      <Label>{label}</Label>
      <div className="mt-1 flex flex-wrap items-center gap-2 p-2 rounded-lg border border-slate-200 bg-white min-h-[44px]" data-testid={testid}>
        {value.map((v) => (
          <span key={v} className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs">
            {v}
            <button onClick={() => onChange(value.filter((x) => x !== v))} className="hover:text-rose-600"><X className="h-3 w-3" /></button>
          </span>
        ))}
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => (e.key === "Enter" || e.key === ",") && (e.preventDefault(), add())}
          placeholder="Add and press Enter"
          className="flex-1 min-w-[120px] outline-none bg-transparent text-sm"
          data-testid={`${testid}-input`}
        />
      </div>
    </div>
  );
}
