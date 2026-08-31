import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Plus, Trash2, Save, FileText, Wand2 } from "lucide-react";
import { toast } from "sonner";

const EMPTY = {
  name: "", description: "", slug: "",
  subjective_hint: "", objective_hint: "", assessment_hint: "", plan_hint: "",
  required_fields: [],
};

export default function ScribeTemplates() {
  const [templates, setTemplates] = useState([]);
  const [editing, setEditing] = useState(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      const { data } = await api.get("/scribe/templates");
      setTemplates(data || []);
    } catch (e) {
      toast.error("Failed to load templates");
    }
  }
  useEffect(() => { load(); }, []);

  async function save() {
    if (!editing.name?.trim()) return toast.info("Name is required.");
    setBusy(true);
    try {
      const payload = { ...editing, required_fields: Array.isArray(editing.required_fields) ? editing.required_fields : String(editing.required_fields || "").split(",").map((s) => s.trim()).filter(Boolean) };
      if (editing.id) {
        await api.patch(`/scribe/templates/${editing.id}`, payload);
        toast.success("Template updated");
      } else {
        await api.post("/scribe/templates", payload);
        toast.success("Template created");
      }
      setEditing(null);
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Save failed");
    } finally { setBusy(false); }
  }

  async function del(t) {
    if (!confirm(`Delete "${t.name}"?`)) return;
    try {
      await api.delete(`/scribe/templates/${t.id}`);
      toast.success("Deleted");
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Delete failed");
    }
  }

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6 lg:py-10 space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Scribe · Template library</div>
          <h1 className="font-serif-display text-3xl sm:text-4xl font-semibold text-emerald-950 tracking-tight mt-1">Match your house style.</h1>
          <p className="text-sm text-slate-600 mt-2 max-w-2xl">
            Every SOAP draft is shaped by the template you pick in the scribe. The five built-in templates cover wellness, dental, dermatology, euthanasia and post-op — edit their guidance or add your own.
          </p>
        </div>
        <Button onClick={() => setEditing({ ...EMPTY })} data-testid="template-new-btn" className="rounded-full bg-emerald-700 hover:bg-emerald-800 text-white">
          <Plus className="h-4 w-4 mr-2" /> New template
        </Button>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        {templates.map((t) => (
          <Card key={t.id} data-testid={`template-card-${t.slug}`} className="p-5 rounded-2xl border-emerald-100 bg-white shadow-sm">
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <FileText className="h-4 w-4 text-emerald-700" />
                  <div className="font-semibold text-emerald-950">{t.name}</div>
                  {t.is_default ? (
                    <Badge variant="outline" className="text-[10px] border-emerald-200 text-emerald-800 bg-emerald-50">Built-in</Badge>
                  ) : (
                    <Badge variant="outline" className="text-[10px] border-amber-200 text-amber-800 bg-amber-50">Custom</Badge>
                  )}
                </div>
                <div className="text-xs text-slate-500">{t.description || "—"}</div>
              </div>
              <div className="flex gap-1">
                <Button variant="outline" size="sm" onClick={() => setEditing(t)} data-testid={`template-edit-${t.slug}`} className="h-8 rounded-full border-emerald-200 text-emerald-800 hover:bg-emerald-50 text-xs">
                  Edit
                </Button>
                {!t.is_default && (
                  <Button variant="outline" size="sm" onClick={() => del(t)} data-testid={`template-delete-${t.slug}`} className="h-8 rounded-full border-rose-200 text-rose-700 hover:bg-rose-50 text-xs px-2">
                    <Trash2 className="h-3 w-3" />
                  </Button>
                )}
              </div>
            </div>
            {t.required_fields?.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {t.required_fields.map((f, i) => (
                  <span key={i} className="text-[10px] uppercase tracking-widest border border-slate-200 rounded-full px-2 py-0.5 text-slate-600 bg-slate-50">{f}</span>
                ))}
              </div>
            )}
          </Card>
        ))}
        {templates.length === 0 && (
          <Card className="p-8 rounded-2xl border-dashed border-emerald-200 bg-white/40 text-center text-sm text-slate-500 md:col-span-2">
            <Wand2 className="h-5 w-5 text-emerald-700 mx-auto mb-2" />
            No templates yet — click "New template" to create your first.
          </Card>
        )}
      </div>

      <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent className="bg-white max-w-2xl" data-testid="template-dialog">
          <DialogHeader>
            <DialogTitle>{editing?.id ? "Edit template" : "New template"}</DialogTitle>
          </DialogHeader>
          {editing && (
            <div className="space-y-3 max-h-[70vh] overflow-y-auto pr-1">
              <div>
                <label className="text-[11px] uppercase tracking-widest text-slate-500 font-semibold">Name</label>
                <Input value={editing.name || ""} onChange={(e) => setEditing({ ...editing, name: e.target.value })} placeholder="Puppy first visit" data-testid="template-name-input" />
              </div>
              <div>
                <label className="text-[11px] uppercase tracking-widest text-slate-500 font-semibold">Description</label>
                <Input value={editing.description || ""} onChange={(e) => setEditing({ ...editing, description: e.target.value })} placeholder="One-line summary of when to use this template" />
              </div>
              {[
                ["subjective_hint", "S — Subjective guidance"],
                ["objective_hint", "O — Objective guidance"],
                ["assessment_hint", "A — Assessment guidance"],
                ["plan_hint", "P — Plan guidance"],
              ].map(([k, label]) => (
                <div key={k}>
                  <label className="text-[11px] uppercase tracking-widest text-slate-500 font-semibold">{label}</label>
                  <Textarea rows={3} value={editing[k] || ""} onChange={(e) => setEditing({ ...editing, [k]: e.target.value })} className="resize-none" data-testid={`template-${k}`} />
                </div>
              ))}
              <div>
                <label className="text-[11px] uppercase tracking-widest text-slate-500 font-semibold">Required fields (comma separated)</label>
                <Input
                  value={Array.isArray(editing.required_fields) ? editing.required_fields.join(", ") : (editing.required_fields || "")}
                  onChange={(e) => setEditing({ ...editing, required_fields: e.target.value })}
                  placeholder="BCS, Weight, Vaccine status"
                  data-testid="template-required-fields"
                />
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditing(null)} className="rounded-full">Cancel</Button>
            <Button onClick={save} disabled={busy} data-testid="template-save-btn" className="rounded-full bg-emerald-700 hover:bg-emerald-800 text-white">
              <Save className="h-4 w-4 mr-2" /> Save template
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
