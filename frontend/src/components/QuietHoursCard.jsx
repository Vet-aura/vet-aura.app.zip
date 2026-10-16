import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Moon, Save } from "lucide-react";
import { cn } from "@/lib/utils";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const ZONES = ["America/New_York", "America/Chicago", "America/Denver", "America/Phoenix", "America/Los_Angeles", "America/Anchorage", "Pacific/Honolulu"];

function pick(p) {
  return {
    quiet_hours_enabled: p.quiet_hours_enabled ?? true,
    quiet_hours_start: p.quiet_hours_start || "21:00",
    quiet_hours_end: p.quiet_hours_end || "08:00",
    quiet_hours_tz: p.quiet_hours_tz || "America/New_York",
    quiet_days: p.quiet_days || [6],
  };
}

function StatusLine({ status, enabled }) {
  if (!enabled) return <span className="text-slate-500">Quiet hours are off — marketing can send any time.</span>;
  if (status?.active) {
    const at = status.next_send_at ? new Date(status.next_send_at).toLocaleString() : "—";
    return <span className="text-amber-800">Quiet hours are active now. Approved blasts queue until <strong>{at}</strong>.</span>;
  }
  return <span className="text-emerald-800">Outside quiet hours — approved blasts send immediately.</span>;
}

export function QuietHoursCard({ profile, saving, onSave }) {
  const [q, setQ] = useState(() => pick(profile));
  useEffect(() => { setQ(pick(profile)); }, [profile]);

  const toggleDay = (i) => setQ((s) => ({ ...s, quiet_days: s.quiet_days.includes(i) ? s.quiet_days.filter((d) => d !== i) : [...s.quiet_days, i].sort() }));

  return (
    <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm" data-testid="quiet-hours-card">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-2">
          <Moon className="h-4 w-4 text-emerald-700" />
          <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Marketing quiet hours</div>
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <Switch checked={q.quiet_hours_enabled} onCheckedChange={(v) => setQ({ ...q, quiet_hours_enabled: v })} data-testid="quiet-enabled" />
          Enforce quiet hours
        </label>
      </div>
      <p className="text-sm text-slate-600 mb-4">Marketing texts never go out inside this window or on quiet days. Care messages (reminders, replies) are transactional and still send.</p>
      <div className={cn("grid sm:grid-cols-3 gap-3 transition-opacity", !q.quiet_hours_enabled && "opacity-50 pointer-events-none")}>
        <label className="text-xs text-slate-600">Quiet from
          <Input type="time" value={q.quiet_hours_start} onChange={(e) => setQ({ ...q, quiet_hours_start: e.target.value })} data-testid="quiet-start" />
        </label>
        <label className="text-xs text-slate-600">Until
          <Input type="time" value={q.quiet_hours_end} onChange={(e) => setQ({ ...q, quiet_hours_end: e.target.value })} data-testid="quiet-end" />
        </label>
        <label className="text-xs text-slate-600">Clinic timezone
          <Select value={q.quiet_hours_tz} onValueChange={(v) => setQ({ ...q, quiet_hours_tz: v })}>
            <SelectTrigger data-testid="quiet-tz"><SelectValue /></SelectTrigger>
            <SelectContent>{ZONES.map((z) => <SelectItem key={z} value={z}>{z.replace("_", " ")}</SelectItem>)}</SelectContent>
          </Select>
        </label>
        <div className="sm:col-span-3">
          <div className="text-xs text-slate-600 mb-1.5">Quiet all day on</div>
          <div className="flex flex-wrap gap-2">
            {DAYS.map((d, i) => (
              <button key={d} type="button" onClick={() => toggleDay(i)} data-testid={`quiet-day-${i}`}
                className={cn("px-3.5 py-1.5 rounded-full text-xs font-semibold border transition-colors",
                  q.quiet_days.includes(i) ? "bg-emerald-800 text-white border-emerald-800" : "bg-white text-slate-700 border-slate-200 hover:border-emerald-300")}>
                {d}
              </button>
            ))}
          </div>
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 mt-5 pt-4 border-t border-emerald-100">
        <div className="text-sm" data-testid="quiet-status"><StatusLine status={profile.quiet_status} enabled={profile.quiet_hours_enabled ?? true} /></div>
        <Button onClick={() => onSave(q)} disabled={saving} data-testid="quiet-save" className="rounded-full bg-emerald-700 hover:bg-emerald-800 text-white">
          <Save className="h-3.5 w-3.5 mr-1.5" /> Save quiet hours
        </Button>
      </div>
    </Card>
  );
}
