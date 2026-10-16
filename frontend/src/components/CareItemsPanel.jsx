import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Syringe, HeartPulse, Check, Trash2, Plus } from "lucide-react";
import { toast } from "sonner";

const daysUntil = (d) => Math.round((new Date(`${d}T00:00:00`) - new Date(new Date().toDateString())) / 86400000);

function DueBadge({ item }) {
  if (item.status === "done") return <Badge variant="outline" className="text-[10px] border-slate-200 text-slate-500">Done</Badge>;
  const n = daysUntil(item.due_date);
  const [label, cls] = n < 0 ? [`${-n}d overdue`, "bg-rose-100 text-rose-800 border-rose-200"]
    : n === 0 ? ["Due today", "bg-amber-100 text-amber-800 border-amber-200"]
    : [`Due in ${n}d`, n <= 14 ? "bg-amber-50 text-amber-800 border-amber-200" : "bg-emerald-50 text-emerald-800 border-emerald-200"];
  return <Badge variant="outline" className={`text-[10px] ${cls}`}>{label}</Badge>;
}

function AddForm({ patientId, onAdded }) {
  const [f, setF] = useState({ kind: "vaccine", name: "", due_date: "" });
  async function add() {
    if (!f.name.trim() || !f.due_date) return toast.info("Name and due date are required.");
    try { await api.post("/reminders/items", { ...f, patient_id: patientId }); setF({ kind: "vaccine", name: "", due_date: "" }); onAdded(); }
    catch { toast.error("Couldn't add care item."); }
  }
  return (
    <div className="grid sm:grid-cols-[140px_1fr_170px_auto] gap-2 pt-4 mt-2 border-t border-emerald-100">
      <Select value={f.kind} onValueChange={(v) => setF({ ...f, kind: v })}>
        <SelectTrigger data-testid="care-item-kind"><SelectValue /></SelectTrigger>
        <SelectContent><SelectItem value="vaccine">Vaccine</SelectItem><SelectItem value="preventive">Preventive</SelectItem></SelectContent>
      </Select>
      <Input placeholder="e.g. Rabies booster" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} data-testid="care-item-name" />
      <Input type="date" value={f.due_date} onChange={(e) => setF({ ...f, due_date: e.target.value })} data-testid="care-item-due" />
      <Button onClick={add} data-testid="care-item-add" className="rounded-full bg-emerald-700 hover:bg-emerald-800 text-white"><Plus className="h-3.5 w-3.5 mr-1" /> Add</Button>
    </div>
  );
}

export function CareItemsPanel({ patientId }) {
  const [items, setItems] = useState([]);
  const load = useCallback(() => api.get(`/reminders/items?patient_id=${patientId}`).then((r) => setItems(r.data)).catch(() => toast.error("Couldn't load care items.")), [patientId]);
  useEffect(() => { load(); }, [load]);

  async function act(id, action) {
    try { action === "delete" ? await api.delete(`/reminders/items/${id}`) : await api.post(`/reminders/items/${id}/complete`); load(); }
    catch { toast.error("Action failed."); }
  }

  return (
    <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm" data-testid="care-items-panel">
      <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold mb-1">Vaccines & preventive care</div>
      <p className="text-sm text-slate-600 mb-3">Due dates here drive automatic reminder texts (see Reminders).</p>
      {items.length === 0 && <div className="text-sm text-slate-500 py-3" data-testid="care-items-empty">No care items yet.</div>}
      {items.map((it) => (
        <div key={it.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5 border-t border-slate-100 first:border-t-0" data-testid={`care-item-${it.id}`}>
          <div className="flex items-center gap-2 min-w-0">
            {it.kind === "vaccine" ? <Syringe className="h-4 w-4 text-emerald-700 shrink-0" /> : <HeartPulse className="h-4 w-4 text-emerald-700 shrink-0" />}
            <span className={`text-sm font-medium ${it.status === "done" ? "text-slate-400 line-through" : "text-emerald-950"}`}>{it.name}</span>
            <span className="text-xs text-slate-500 font-mono-clinical">{it.due_date}</span>
            <DueBadge item={it} />
          </div>
          <div className="flex gap-1">
            {it.status !== "done" && <Button size="sm" variant="ghost" onClick={() => act(it.id, "complete")} data-testid={`care-item-complete-${it.id}`} className="h-7 text-xs text-emerald-800"><Check className="h-3 w-3 mr-1" /> Done</Button>}
            <Button size="sm" variant="ghost" onClick={() => act(it.id, "delete")} data-testid={`care-item-delete-${it.id}`} className="h-7 text-xs text-slate-500"><Trash2 className="h-3 w-3" /></Button>
          </div>
        </div>
      ))}
      <AddForm patientId={patientId} onAdded={load} />
    </Card>
  );
}
