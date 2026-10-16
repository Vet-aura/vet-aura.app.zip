import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Save } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

const OFFSETS = [30, 14, 7, 3, 1, 0, -3, -7, -14];
const offsetLabel = (o) => (o > 0 ? `${o}d before` : o === 0 ? "On due date" : `${-o}d overdue`);
const HOURS = Array.from({ length: 15 }, (_, i) => i + 6);

export function ReminderSettingsCard({ settings, isOwner, onSaved }) {
  const [s, setS] = useState(settings);
  const [busy, setBusy] = useState(false);
  useEffect(() => { setS(settings); }, [settings]);

  const toggle = (o) => setS((x) => ({ ...x, offsets: x.offsets.includes(o) ? x.offsets.filter((y) => y !== o) : [...x.offsets, o] }));

  async function save() {
    if (!s.offsets.length) return toast.info("Pick at least one reminder step.");
    setBusy(true);
    try {
      await api.put("/reminders/settings", { enabled: s.enabled, offsets: s.offsets, send_hour: s.send_hour, template: s.template });
      toast.success("Reminder rules saved.");
      onSaved();
    } catch (e) {
      const d = e?.response?.data?.detail;
      toast.error(typeof d === "string" ? d : Array.isArray(d) ? d.map((x) => (x.msg || "").replace(/^Value error, /, "")).join(" ") : "Couldn't save.");
    } finally { setBusy(false); }
  }

  return (
    <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm space-y-4" data-testid="reminder-settings-card">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Reminder rules</div>
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <Switch checked={s.enabled} disabled={!isOwner} onCheckedChange={(v) => setS({ ...s, enabled: v })} data-testid="reminders-enabled" /> Automatic reminders
        </label>
      </div>
      <div>
        <div className="text-xs text-slate-600 mb-1.5">Text the owner</div>
        <div className="flex flex-wrap gap-2">
          {OFFSETS.map((o) => (
            <button key={o} type="button" disabled={!isOwner} onClick={() => toggle(o)} data-testid={`reminder-offset-${o}`}
              className={cn("px-3 py-1.5 rounded-full text-xs font-semibold border transition-colors",
                s.offsets.includes(o) ? "bg-emerald-800 text-white border-emerald-800" : "bg-white text-slate-700 border-slate-200 hover:border-emerald-300")}>
              {offsetLabel(o)}
            </button>
          ))}
        </div>
      </div>
      <label className="block text-xs text-slate-600">Daily send time (clinic local time; skipped on quiet days)
        <Select value={String(s.send_hour)} disabled={!isOwner} onValueChange={(v) => setS({ ...s, send_hour: Number(v) })}>
          <SelectTrigger className="mt-1 w-40" data-testid="reminder-send-hour"><SelectValue /></SelectTrigger>
          <SelectContent>{HOURS.map((h) => <SelectItem key={h} value={String(h)}>{`${h % 12 || 12}:00 ${h < 12 ? "AM" : "PM"}`}</SelectItem>)}</SelectContent>
        </Select>
      </label>
      <label className="block text-xs text-slate-600">Message
        <Textarea rows={3} maxLength={400} disabled={!isOwner} value={s.template} onChange={(e) => setS({ ...s, template: e.target.value })} data-testid="reminder-template" className="mt-1" />
        <span className="text-[11px] text-slate-500">Fields: {"{first_name} {pet_name} {item} {due_phrase} {due_date} {clinic_name}"}. Clinic name + "Reply STOP to opt out." are appended.</span>
      </label>
      {isOwner
        ? <div className="flex justify-end"><Button onClick={save} disabled={busy} data-testid="reminder-settings-save" className="rounded-full bg-emerald-700 hover:bg-emerald-800 text-white"><Save className="h-3.5 w-3.5 mr-1.5" /> Save rules</Button></div>
        : <div className="text-xs text-slate-500">Only clinic owners can change reminder rules.</div>}
    </Card>
  );
}
