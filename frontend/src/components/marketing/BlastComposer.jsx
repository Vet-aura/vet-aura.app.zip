import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Megaphone, Send, Users } from "lucide-react";
import { toast } from "sonner";
import { errMsg } from "./TemplateManager";

const EXCLUDE_LABELS = { no_consent: "No marketing consent", opted_out: "Opted out", no_phone: "No phone", duplicate: "Duplicate phone" };

function AudiencePreview({ preview }) {
  if (!preview) return null;
  return (
    <div className="rounded-xl border border-emerald-100 bg-emerald-50/30 p-4" data-testid="audience-preview">
      <div className="flex items-center gap-2 text-sm font-semibold text-emerald-950"><Users className="h-4 w-4" /> <span data-testid="audience-eligible-count">{preview.eligible_count}</span> clients with marketing consent</div>
      <div className="flex flex-wrap gap-2 mt-2">
        {Object.entries(preview.excluded).filter(([, n]) => n > 0).map(([k, n]) => (
          <span key={k} className="text-[11px] px-2 py-0.5 rounded-full bg-white border border-slate-200 text-slate-600" data-testid={`audience-excluded-${k}`}>{EXCLUDE_LABELS[k]}: {n} excluded</span>
        ))}
      </div>
      {preview.sample.map((r) => (
        <div key={r.phone_e164} className="mt-3 text-sm"><span className="font-mono-clinical text-xs text-slate-500">{r.phone_e164}</span><div className="text-slate-800">{r.body} <span className="text-slate-400">Reply STOP to opt out.</span></div></div>
      ))}
    </div>
  );
}

export function BlastComposer({ templates, onCreated }) {
  const [form, setForm] = useState({ name: "", template_id: "", species: "all" });
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!form.template_id) { setPreview(null); return; }
    let live = true;
    api.post("/sms/marketing/audience/preview", { template_id: form.template_id, species: form.species })
      .then((r) => live && setPreview(r.data))
      .catch((e) => live && toast.error(errMsg(e, "Couldn't load audience.")));
    return () => { live = false; };
  }, [form.template_id, form.species]);

  async function submit() {
    if (!form.name.trim() || !form.template_id) return toast.info("Name the blast and pick a template.");
    setBusy(true);
    try {
      await api.post("/sms/marketing/campaigns", form);
      toast.success("Sent for owner approval.");
      setForm({ name: "", template_id: "", species: "all" });
      onCreated();
    } catch (e) { toast.error(errMsg(e, "Couldn't create blast.")); } finally { setBusy(false); }
  }

  return (
    <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm space-y-3" data-testid="composer-card">
      <div className="flex items-center gap-2"><Megaphone className="h-4 w-4 text-emerald-700" /><div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Compose a blast</div></div>
      <Input placeholder="Blast name, e.g. February dental promo" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="blast-name" />
      <div className="grid sm:grid-cols-2 gap-3">
        <Select value={form.template_id} onValueChange={(v) => setForm({ ...form, template_id: v })}>
          <SelectTrigger data-testid="blast-template"><SelectValue placeholder="Pick a locked template" /></SelectTrigger>
          <SelectContent>{templates.map((t) => <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={form.species} onValueChange={(v) => setForm({ ...form, species: v })}>
          <SelectTrigger data-testid="blast-species"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All pet owners</SelectItem>
            <SelectItem value="Canine">Dog owners</SelectItem>
            <SelectItem value="Feline">Cat owners</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <AudiencePreview preview={preview} />
      <div className="flex justify-end">
        <Button onClick={submit} disabled={busy || !preview?.eligible_count} data-testid="blast-submit" className="rounded-full bg-emerald-700 hover:bg-emerald-800 text-white"><Send className="h-3.5 w-3.5 mr-1.5" /> Request approval</Button>
      </div>
    </Card>
  );
}
