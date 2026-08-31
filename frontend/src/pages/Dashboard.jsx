import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Mic, ArrowRight, AlertTriangle, PawPrint, Clock, MessagesSquare } from "lucide-react";

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [appts, setAppts] = useState([]);
  const [patients, setPatients] = useState([]);
  const [msgs, setMsgs] = useState([]);

  useEffect(() => {
    Promise.all([
      api.get("/stats").then((r) => setStats(r.data)),
      api.get("/appointments").then((r) => setAppts(r.data)),
      api.get("/patients").then((r) => setPatients(r.data)),
      api.get("/messages").then((r) => setMsgs(r.data)),
    ]).catch(() => {});
  }, []);

  const alerts = patients.flatMap((p) => (p.alerts || []).map((a) => ({ pet: p.name, alert: a, id: p.id })));

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 lg:py-10 space-y-8">
      {/* Hero header */}
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
        <div>
          <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Good morning, Dr. Reyes</div>
          <h1 className="mt-1 font-serif-display text-3xl sm:text-4xl lg:text-5xl font-semibold text-emerald-950 tracking-tight">
            Your clinic, at a glance.
          </h1>
        </div>
        <Link to="/app/scribe" data-testid="dashboard-start-scribe">
          <Button className="bg-emerald-700 hover:bg-emerald-800 text-white rounded-full h-11 px-5">
            <Mic className="mr-2 h-4 w-4" /> Start ambient scribe
          </Button>
        </Link>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: "Patients", value: stats?.patients ?? "—", tid: "kpi-patients", icon: PawPrint },
          { label: "Appointments today", value: stats?.appointments_today ?? "—", tid: "kpi-appts", icon: Clock },
          { label: "Open messages", value: stats?.open_messages ?? "—", tid: "kpi-messages", icon: MessagesSquare },
          { label: "Draft notes", value: stats?.draft_notes ?? 0, tid: "kpi-drafts", icon: Mic },
        ].map((k) => (
          <Card key={k.label} className="p-5 border-emerald-100 shadow-sm bg-white rounded-2xl" data-testid={k.tid}>
            <div className="flex items-center justify-between">
              <div className="text-[11px] uppercase tracking-widest text-slate-500 font-semibold">{k.label}</div>
              <k.icon className="h-4 w-4 text-emerald-700" />
            </div>
            <div className="mt-2 font-serif-display text-3xl text-emerald-950">{k.value}</div>
          </Card>
        ))}
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Today */}
        <Card className="lg:col-span-2 p-6 rounded-2xl bg-white border-emerald-100 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-serif-display text-xl font-semibold text-emerald-950">Today's schedule</h2>
            <Link to="/app/schedule" className="text-xs font-semibold text-emerald-700 hover:text-emerald-900 flex items-center gap-1" data-testid="dashboard-view-schedule">
              View all <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          <div className="divide-y divide-emerald-50">
            {appts.slice(0, 5).map((a) => (
              <div key={a.id} className="py-3 flex items-center gap-4" data-testid={`appt-row-${a.id}`}>
                <div className="font-mono-clinical text-sm text-emerald-900 w-16">
                  {new Date(a.datetime).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-slate-900 truncate">{a.patient?.name} · <span className="text-slate-500 font-normal">{a.patient?.breed}</span></div>
                  <div className="text-xs text-slate-500 truncate">{a.reason}</div>
                </div>
                <Badge variant="outline" className="border-emerald-200 text-emerald-800 bg-emerald-50 hidden sm:inline-flex">{a.type}</Badge>
                <div className="text-xs text-slate-500 hidden md:block">{a.vet} · {a.room}</div>
              </div>
            ))}
            {appts.length === 0 && <div className="py-6 text-sm text-slate-500 text-center">No appointments loaded.</div>}
          </div>
        </Card>

        {/* Alerts */}
        <Card className="p-6 rounded-2xl bg-white border-emerald-100 shadow-sm">
          <h2 className="font-serif-display text-xl font-semibold text-emerald-950 mb-4">Alerts & pending</h2>
          <div className="space-y-3">
            {alerts.slice(0, 6).map((a, i) => (
              <div key={i} className="flex items-start gap-3 p-3 rounded-xl bg-amber-50/60 border border-amber-100" data-testid={`alert-${i}`}>
                <AlertTriangle className="h-4 w-4 text-amber-700 mt-0.5 flex-shrink-0" />
                <div className="text-sm">
                  <div className="font-semibold text-amber-900">{a.pet}</div>
                  <div className="text-amber-800 text-xs">{a.alert}</div>
                </div>
              </div>
            ))}
            {alerts.length === 0 && <div className="text-sm text-slate-500">All caught up.</div>}
          </div>

          <h3 className="mt-6 mb-3 text-xs uppercase tracking-widest text-slate-500 font-semibold">Client messages</h3>
          <div className="space-y-2">
            {msgs.slice(0, 3).map((m) => (
              <Link to="/app/inbox" key={m.id} className="block p-3 rounded-xl border border-slate-100 hover:border-emerald-200 hover:bg-emerald-50/40 transition-all" data-testid={`msg-preview-${m.id}`}>
                <div className="text-xs text-slate-500">{m.channel} · {m.patient?.name}</div>
                <div className="text-sm font-medium text-slate-800 truncate">{m.subject}</div>
              </Link>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
