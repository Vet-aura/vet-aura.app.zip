import { useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Lock, Plus, Archive } from "lucide-react";
import { toast } from "sonner";

const errMsg = (e, fb) => {
  const d = e?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => (x?.msg || "").replace(/^Value error, /, "")).filter(Boolean).join(" ");
  return fb;
};

export function TemplateManager({ templates, isOwner, onChange }) {
  const [form, setForm] = useState({ name: "", body: "" });
  const [busy, setBusy] = useState(false);

  async function create() {
    if (!form.name.trim() || !form.body.trim()) return toast.info("Name and message are required.");
    setBusy(true);
    try {
      await api.post("/sms/marketing/templates", form);
      setForm({ name: "", body: "" });
      toast.success("Template locked and ready.");
      onChange();
    } catch (e) { toast.error(errMsg(e, "Couldn't create template.")); } finally { setBusy(false); }
  }

  async function archive(id) {
    if (!window.confirm("Archive this template? Existing blasts keep their copy.")) return;
    try { await api.delete(`/sms/marketing/templates/${id}`); onChange(); }
    catch (e) { toast.error(errMsg(e, "Couldn't archive.")); }
  }

  return (
    <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm" data-testid="templates-card">
      <div className="flex items-center gap-2 mb-1"><Lock className="h-4 w-4 text-emerald-700" /><div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Locked templates</div></div>
      <p className="text-sm text-slate-600 mb-4">Staff can only send these exact words. Merge fields: <code className="font-mono-clinical text-xs">{"{first_name}"}</code> <code className="font-mono-clinical text-xs">{"{pet_name}"}</code> <code className="font-mono-clinical text-xs">{"{clinic_name}"}</code>. Your clinic name (unless merged) and "Reply STOP to opt out." are appended automatically.</p>
      <div className="space-y-2">
        {templates.length === 0 && <div className="text-sm text-slate-500 py-3" data-testid="templates-empty">No templates yet.{isOwner ? " Create your first one below." : " Ask a clinic owner to add one."}</div>}
        {templates.map((t) => (
          <div key={t.id} className="p-3 rounded-xl border border-emerald-100 bg-emerald-50/30" data-testid={`template-${t.id}`}>
            <div className="flex items-center justify-between gap-2">
              <div className="text-sm font-semibold text-emerald-950">{t.name}</div>
              {isOwner && <Button size="sm" variant="ghost" onClick={() => archive(t.id)} data-testid={`template-archive-${t.id}`} className="h-7 text-xs text-slate-500"><Archive className="h-3 w-3 mr-1" /> Archive</Button>}
            </div>
            <div className="text-sm text-slate-700 mt-1 whitespace-pre-wrap">{t.body}</div>
          </div>
        ))}
      </div>
      {isOwner && (
        <div className="mt-5 pt-4 border-t border-emerald-100 space-y-2">
          <Input placeholder="Template name, e.g. Spring dental month" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="template-name" />
          <Textarea rows={3} maxLength={480} placeholder="Hi {first_name}! February is dental month — 15% off {pet_name}'s cleaning." value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} data-testid="template-body" />
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-500">{form.body.length}/480</span>
            <Button onClick={create} disabled={busy} data-testid="template-create" className="rounded-full bg-emerald-700 hover:bg-emerald-800 text-white"><Plus className="h-3.5 w-3.5 mr-1.5" /> Create & lock</Button>
          </div>
        </div>
      )}
    </Card>
  );
}

export { errMsg };
