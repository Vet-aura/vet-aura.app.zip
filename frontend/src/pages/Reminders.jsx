import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthProvider";
import { Button } from "@/components/ui/button";
import { ReminderSettingsCard } from "@/components/reminders/ReminderSettingsCard";
import { UpcomingQueue, SendLog } from "@/components/reminders/ReminderLists";
import { Play } from "lucide-react";
import { toast } from "sonner";

export default function Reminders() {
  const { user } = useAuth();
  const isOwner = (user?.role || "owner") === "owner";
  const [settings, setSettings] = useState(null);
  const [upcoming, setUpcoming] = useState([]);
  const [log, setLog] = useState([]);
  const [running, setRunning] = useState(false);

  const load = useCallback(async () => {
    try {
      const [s, u, l] = await Promise.all([api.get("/reminders/settings"), api.get("/reminders/upcoming?days=30"), api.get("/reminders/log")]);
      setSettings(s.data); setUpcoming(u.data); setLog(l.data);
    } catch { toast.error("Couldn't load reminders."); }
  }, []);
  useEffect(() => { load(); }, [load]);

  async function runNow() {
    setRunning(true);
    try {
      const { data } = await api.post("/reminders/run");
      toast.success(`Run complete: ${data.sent} sent, ${data.blocked} blocked, ${data.failed} failed.`);
      load();
    } catch { toast.error("Run failed."); } finally { setRunning(false); }
  }

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6 lg:py-10 space-y-6" data-testid="reminders-page">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Care reminders</div>
          <h1 className="font-serif-display text-3xl sm:text-4xl font-semibold text-emerald-950 tracking-tight mt-1">Due dates that text themselves.</h1>
          <p className="text-sm text-slate-600 mt-2 max-w-2xl">Vaccine and preventive-care due dates become care texts from your clinic's number. Only owners with care consent are texted, and each step is sent once.</p>
        </div>
        {isOwner && <Button onClick={runNow} disabled={running} data-testid="reminders-run-now" className="rounded-full bg-emerald-900 hover:bg-emerald-950 text-white"><Play className="h-3.5 w-3.5 mr-1.5" /> {running ? "Running…" : "Run now"}</Button>}
      </div>
      {settings?.last_run_date && <div className="text-xs text-slate-500" data-testid="reminders-last-run">Last run: {settings.last_run_date}</div>}
      <div className="grid lg:grid-cols-[1fr_1.1fr] gap-6 items-start">
        <div className="space-y-6">
          {settings && <ReminderSettingsCard settings={settings} isOwner={isOwner} onSaved={load} />}
          <UpcomingQueue rows={upcoming} />
        </div>
        <SendLog rows={log} />
      </div>
    </div>
  );
}
