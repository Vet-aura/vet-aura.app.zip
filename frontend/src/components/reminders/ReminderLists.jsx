import { Link } from "react-router-dom";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const stageLabel = (o) => (o > 0 ? `${o}d before` : o === 0 ? "Due date" : `${-o}d overdue`);
const STATUS_CLS = {
  sent: "bg-emerald-100 text-emerald-800 border-emerald-200",
  blocked: "bg-amber-100 text-amber-800 border-amber-200",
  failed: "bg-rose-100 text-rose-800 border-rose-200",
  processing: "bg-slate-100 text-slate-600 border-slate-200",
};

export function UpcomingQueue({ rows }) {
  return (
    <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm" data-testid="reminder-upcoming">
      <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold mb-3">Next 30 days</div>
      {rows.length === 0 && <div className="text-sm text-slate-500 py-3" data-testid="reminder-upcoming-empty">Nothing scheduled.</div>}
      {rows.map((r) => (
        <div key={`${r.item_id}-${r.stage}`} className="flex flex-wrap items-center justify-between gap-2 py-2.5 border-t border-slate-100 first:border-t-0" data-testid={`upcoming-${r.item_id}`}>
          <div className="min-w-0">
            <div className="text-sm font-medium text-emerald-950"><Link to={`/app/patients/${r.patient_id}`} className="hover:underline">{r.patient_name}</Link> · {r.item_name}</div>
            <div className="text-xs text-slate-500">{r.owner_name} · due {r.due_date} · {stageLabel(r.stage)}</div>
          </div>
          <div className="flex items-center gap-2">
            {r.care_consent !== "opted_in" && <Badge variant="outline" className="text-[10px] bg-amber-50 text-amber-800 border-amber-200" data-testid={`upcoming-consent-${r.item_id}`}>No care consent</Badge>}
            <span className="text-xs font-mono-clinical text-slate-600">{r.send_on}</span>
          </div>
        </div>
      ))}
    </Card>
  );
}

export function SendLog({ rows }) {
  return (
    <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm" data-testid="reminder-log">
      <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold mb-3">Send log</div>
      {rows.length === 0 && <div className="text-sm text-slate-500 py-3" data-testid="reminder-log-empty">No reminders sent yet.</div>}
      {rows.slice(0, 50).map((r) => (
        <div key={r.id} className="py-3 border-t border-slate-100 first:border-t-0 space-y-1" data-testid={`reminder-log-${r.id}`}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="text-sm font-medium text-emerald-950">{r.patient_name} · {r.item_name} <span className="text-xs text-slate-500 font-normal">({stageLabel(r.stage)}, {r.trigger})</span></div>
            <Badge variant="outline" className={`text-[10px] ${STATUS_CLS[r.status] || ""}`}>{r.status}</Badge>
          </div>
          <div className="text-xs text-slate-600">{r.body}</div>
          <div className="text-[11px] text-slate-400">{r.phone_e164} · {new Date(r.at).toLocaleString()}{r.reason ? ` · ${r.reason}` : ""}</div>
        </div>
      ))}
    </Card>
  );
}
