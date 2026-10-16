import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ShieldAlert, Check } from "lucide-react";
import { toast } from "sonner";

function AlertRow({ a, onAck }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 py-3 border-t border-slate-100" data-testid={`security-alert-${a.id}`}>
      <div className="min-w-0">
        <div className="text-sm font-medium text-slate-900 break-all">{a.email} locked out after {a.failed_attempts} failed attempts</div>
        <div className="text-xs text-slate-500 mt-0.5">IP {a.ip} · {new Date(a.at).toLocaleString()}</div>
      </div>
      {a.acknowledged
        ? <Badge variant="outline" className="text-[10px] border-slate-200 text-slate-500">Reviewed by {a.acknowledged_by}</Badge>
        : <Button size="sm" variant="outline" onClick={() => onAck(a.id)} data-testid={`security-alert-ack-${a.id}`} className="h-7 text-xs rounded-full border-emerald-300 text-emerald-800"><Check className="h-3 w-3 mr-1" /> Mark reviewed</Button>}
    </div>
  );
}

export function SecurityAlertsCard() {
  const [alerts, setAlerts] = useState(null);
  const load = useCallback(async () => {
    try { setAlerts((await api.get("/security/alerts")).data); }
    catch { setAlerts([]); toast.error("Couldn't load security alerts."); }
  }, []);
  useEffect(() => { load(); }, [load]);

  async function ack(id) {
    try { await api.post(`/security/alerts/${id}/ack`); await load(); }
    catch { toast.error("Couldn't update alert."); }
  }

  const open = (alerts || []).filter((a) => !a.acknowledged).length;
  return (
    <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm" data-testid="security-alerts-card">
      <div className="flex items-center justify-between mb-2">
        <div className="text-xs uppercase tracking-widest text-slate-500 font-semibold flex items-center gap-2"><ShieldAlert className="h-3 w-3" /> Security alerts</div>
        {open > 0 && <Badge className="bg-rose-100 text-rose-800 border-rose-200" data-testid="security-alerts-open-count">{open} to review</Badge>}
      </div>
      <div className="text-sm text-slate-600 mb-2">After 5 failed sign-ins in 15 minutes an account is locked for 15 minutes. The clinic owner is emailed when your email provider is connected.</div>
      {alerts === null && <div className="text-sm text-slate-400 py-4">Loading…</div>}
      {alerts?.length === 0 && <div className="text-sm text-slate-500 py-4" data-testid="security-alerts-empty">No lockouts. All quiet.</div>}
      {(alerts || []).slice(0, 20).map((a) => <AlertRow key={a.id} a={a} onAck={ack} />)}
    </Card>
  );
}
