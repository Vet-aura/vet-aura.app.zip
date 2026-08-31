import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Sparkles, Plus, Check, X, AlertOctagon, Clock, ListTodo } from "lucide-react";
import { toast } from "sonner";

const PRIORITY_STYLE = {
  urgent: "bg-rose-100 text-rose-800 border-rose-200",
  high: "bg-amber-100 text-amber-800 border-amber-200",
  normal: "bg-emerald-100 text-emerald-800 border-emerald-200",
  low: "bg-slate-100 text-slate-700 border-slate-200",
};

const SOURCE_LABEL = {
  auto_postop: "Post-op",
  auto_chronic: "Chronic monitoring",
  auto_alert: "Care alert",
  auto_stale_msg: "Stale message",
  message: "From message",
  manual: "Manual",
};

function bucketFor(t) {
  const now = new Date();
  const due = new Date(t.due_date);
  const dayDiff = Math.floor((due - now) / 86400000);
  if (t.priority === "urgent") return "urgent";
  if (dayDiff < 0) return "overdue";
  if (dayDiff <= 1) return "today";
  if (dayDiff <= 7) return "week";
  return "later";
}

const BUCKETS = [
  { key: "urgent", label: "Urgent", icon: AlertOctagon, cls: "text-rose-800" },
  { key: "overdue", label: "Overdue", icon: Clock, cls: "text-amber-800" },
  { key: "today", label: "Today", icon: Clock, cls: "text-emerald-800" },
  { key: "week", label: "This week", icon: Clock, cls: "text-slate-800" },
  { key: "later", label: "Later", icon: Clock, cls: "text-slate-500" },
];

export default function Tasks() {
  const [tasks, setTasks] = useState([]);
  const [showDone, setShowDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
  const [patients, setPatients] = useState([]);
  const [form, setForm] = useState({ title: "", description: "", patient_id: "", priority: "normal" });

  async function load() {
    const { data } = await api.get("/tasks");
    setTasks(data);
  }
  useEffect(() => {
    load();
    api.get("/patients").then((r) => setPatients(r.data)).catch(() => {});
  }, []);

  async function autoGenerate() {
    setBusy(true);
    try {
      const { data } = await api.post("/tasks/auto-generate");
      toast.success(data.created ? `${data.created} follow-up tasks created` : "Everything's covered — no new tasks");
      await load();
    } catch {
      toast.error("Auto-generate failed");
    } finally {
      setBusy(false);
    }
  }

  async function updateStatus(id, status) {
    await api.patch(`/tasks/${id}`, { status });
    await load();
  }

  async function saveManual() {
    if (!form.title) return toast.info("Give the task a title");
    await api.post("/tasks", { ...form, patient_id: form.patient_id || null });
    setOpen(false);
    setForm({ title: "", description: "", patient_id: "", priority: "normal" });
    await load();
    toast.success("Task added");
  }

  const visible = tasks.filter((t) => (showDone ? true : t.status === "open"));
  const grouped = BUCKETS.map((b) => ({ ...b, items: visible.filter((t) => t.status === "open" && bucketFor(t) === b.key) }));
  const done = visible.filter((t) => t.status !== "open");

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6 lg:py-10 space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
        <div>
          <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Follow-ups</div>
          <h1 className="font-serif-display text-3xl sm:text-4xl font-semibold text-emerald-950 tracking-tight mt-1">Nothing falls through the cracks.</h1>
          <p className="text-sm text-slate-600 mt-2 max-w-2xl">Vetaura scans your patients and messages every time you tap Auto-generate — post-ops, chronic monitoring, care alerts and stale messages become concrete tasks with owners attached.</p>
        </div>
        <div className="flex gap-2">
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button variant="outline" className="rounded-full border-emerald-300 text-emerald-800 hover:bg-emerald-50" data-testid="tasks-new-btn"><Plus className="h-4 w-4 mr-2" /> New task</Button>
            </DialogTrigger>
            <DialogContent className="bg-white">
              <DialogHeader><DialogTitle>New follow-up task</DialogTitle></DialogHeader>
              <div className="space-y-3">
                <Input placeholder="Title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} data-testid="tasks-title" />
                <Textarea placeholder="Description (optional)" rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} data-testid="tasks-desc" />
                <div className="grid grid-cols-2 gap-2">
                  <Select value={form.patient_id} onValueChange={(v) => setForm({ ...form, patient_id: v })}>
                    <SelectTrigger data-testid="tasks-patient"><SelectValue placeholder="Patient (optional)" /></SelectTrigger>
                    <SelectContent>{patients.map((p) => <SelectItem key={p.id} value={p.id}>{p.name} · {p.breed}</SelectItem>)}</SelectContent>
                  </Select>
                  <Select value={form.priority} onValueChange={(v) => setForm({ ...form, priority: v })}>
                    <SelectTrigger data-testid="tasks-priority"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="urgent">Urgent</SelectItem>
                      <SelectItem value="high">High</SelectItem>
                      <SelectItem value="normal">Normal</SelectItem>
                      <SelectItem value="low">Low</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <DialogFooter>
                <Button onClick={saveManual} data-testid="tasks-save" className="bg-emerald-700 hover:bg-emerald-800 text-white rounded-full">Add task</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
          <Button onClick={autoGenerate} disabled={busy} data-testid="tasks-auto-generate" className="bg-emerald-700 hover:bg-emerald-800 text-white rounded-full">
            <Sparkles className="h-4 w-4 mr-2" /> {busy ? "Scanning…" : "Auto-generate"}
          </Button>
        </div>
      </div>

      {grouped.map((b) => b.items.length > 0 && (
        <div key={b.key} data-testid={`tasks-bucket-${b.key}`}>
          <div className={`flex items-center gap-2 text-xs uppercase tracking-widest font-semibold mb-2 ${b.cls}`}>
            <b.icon className="h-3 w-3" /> {b.label} <span className="text-slate-400">({b.items.length})</span>
          </div>
          <Card className="p-2 rounded-2xl border-emerald-100 bg-white shadow-sm">
            <div className="divide-y divide-emerald-50">
              {b.items.map((t) => (
                <div key={t.id} className="flex items-start gap-3 p-3" data-testid={`task-${t.id}`}>
                  <button
                    onClick={() => updateStatus(t.id, "completed")}
                    className="mt-0.5 h-6 w-6 rounded-md border-2 border-emerald-300 hover:bg-emerald-50 grid place-items-center text-emerald-700 transition-all flex-shrink-0"
                    data-testid={`task-complete-${t.id}`}
                    aria-label="Complete"
                  >
                    <Check className="h-4 w-4 opacity-0 hover:opacity-100" />
                  </button>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <div className="font-semibold text-slate-900 truncate">{t.title}</div>
                      <Badge className={`text-[10px] border ${PRIORITY_STYLE[t.priority] || PRIORITY_STYLE.normal}`}>{t.priority}</Badge>
                      {t.patient && <Badge variant="outline" className="text-[10px] border-emerald-200 text-emerald-800 bg-emerald-50">{t.patient.name}</Badge>}
                      <Badge variant="outline" className="text-[10px] border-slate-200 text-slate-600 bg-slate-50">{SOURCE_LABEL[t.source] || t.source}</Badge>
                    </div>
                    {t.description && <div className="text-xs text-slate-600 mt-1 line-clamp-2">{t.description}</div>}
                    <div className="text-[10px] font-mono-clinical text-slate-400 uppercase tracking-widest mt-1">Due {new Date(t.due_date).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</div>
                  </div>
                  <button onClick={() => updateStatus(t.id, "dismissed")} className="text-slate-300 hover:text-rose-500 p-1" data-testid={`task-dismiss-${t.id}`} aria-label="Dismiss">
                    <X className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>
          </Card>
        </div>
      ))}

      {grouped.every((b) => b.items.length === 0) && (
        <Card className="p-10 rounded-2xl border-emerald-100 bg-white text-center text-slate-500">
          <ListTodo className="h-8 w-8 text-slate-300 mx-auto mb-2" />
          Nothing open. Tap <span className="font-semibold text-emerald-800">Auto-generate</span> to scan for post-op check-ins, chronic monitoring, care alerts and stale messages.
        </Card>
      )}

      <div className="flex items-center gap-2">
        <Button variant="ghost" size="sm" onClick={() => setShowDone((v) => !v)} data-testid="tasks-toggle-done" className="text-xs">
          {showDone ? "Hide" : "Show"} completed ({tasks.filter((t) => t.status !== "open").length})
        </Button>
      </div>
      {showDone && done.length > 0 && (
        <Card className="p-3 rounded-2xl border-emerald-50 bg-emerald-50/40">
          <div className="divide-y divide-emerald-100/60">
            {done.map((t) => (
              <div key={t.id} className="flex items-start gap-3 p-3 opacity-60">
                <div className="h-6 w-6 rounded-md bg-emerald-600 grid place-items-center text-white"><Check className="h-4 w-4" /></div>
                <div className="flex-1 line-through text-slate-600 text-sm">{t.title}</div>
                <div className="text-[10px] text-slate-400 font-mono-clinical">{new Date(t.completed_at || t.due_date).toLocaleDateString()}</div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
