import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";

function Stat({ label, value, sub, tid }) {
  return (
    <div className="rounded-xl border border-emerald-100 bg-emerald-50/40 p-3" data-testid={tid}>
      <div className="text-[11px] uppercase tracking-wider text-slate-500">{label}</div>
      <div className="text-2xl font-semibold text-emerald-950 font-serif-display">{value}</div>
      {sub && <div className="text-[11px] text-slate-500">{sub}</div>}
    </div>
  );
}

const fmt = (iso) => (iso ? new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" }) : "—");

function Row({ r }) {
  return (
    <div className="py-3 border-t border-slate-100 text-sm" data-testid={`result-row-${r.owner_id}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div><span className="font-medium text-emerald-950">{r.name}</span> <span className="text-xs text-slate-500 font-mono-clinical">{r.phone_e164}</span></div>
        <Badge variant="outline" className="text-[10px]">{r.status}</Badge>
      </div>
      {r.reason && <div className="text-xs text-slate-500 mt-0.5 break-words">{r.reason}</div>}
      {r.status === "sent" && (
        <div className="flex flex-wrap gap-3 text-xs mt-1">
          <span className={r.replied ? "text-emerald-800" : "text-slate-400"}>Replied: {r.replied ? fmt(r.replied.at) : "no"}</span>
          <span className={r.opted_out_at ? "text-rose-700" : "text-slate-400"}>Opted out: {r.opted_out_at ? fmt(r.opted_out_at) : "no"}</span>
          <span className={r.booked_at ? "text-emerald-800 font-semibold" : "text-slate-400"}>Booked: {r.booked_at ? fmt(r.booked_at) : "no"}</span>
        </div>
      )}
      {r.replied?.text && <div className="text-xs text-slate-600 italic mt-1">"{r.replied.text}"</div>}
    </div>
  );
}

export function CampaignResultsSheet({ campaignId, onClose }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    if (!campaignId) return;
    setData(null);
    api.get(`/sms/marketing/campaigns/${campaignId}/results`).then((r) => setData(r.data)).catch(() => toast.error("Couldn't load results."));
  }, [campaignId]);
  const s = data?.summary;

  return (
    <Sheet open={!!campaignId} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full sm:max-w-xl overflow-y-auto" data-testid="campaign-results-sheet">
        <SheetHeader>
          <SheetTitle className="font-serif-display text-emerald-950">{data?.campaign?.name || "Results"}</SheetTitle>
          <SheetDescription>Replies count within 7 days, bookings (appointments or visits for the client's pets) within 30 days of each send.</SheetDescription>
        </SheetHeader>
        {!data && <div className="text-sm text-slate-400 py-6">Loading…</div>}
        {s && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-5">
            <Stat label="Reached" value={s.sent} sub={`of ${s.recipients}`} tid="results-sent" />
            <Stat label="Replied" value={`${s.reply_rate}%`} sub={`${s.replied} client${s.replied === 1 ? "" : "s"}`} tid="results-replied" />
            <Stat label="Booked" value={`${s.booking_rate}%`} sub={`${s.booked} client${s.booked === 1 ? "" : "s"}`} tid="results-booked" />
            <Stat label="Opted out" value={`${s.opt_out_rate}%`} sub={`${s.opted_out} client${s.opted_out === 1 ? "" : "s"}`} tid="results-opted-out" />
          </div>
        )}
        {s && (s.blocked > 0 || s.failed > 0) && <div className="text-xs text-slate-500 mt-2" data-testid="results-not-reached">{s.blocked} blocked · {s.failed} failed</div>}
        <div className="mt-4">{(data?.rows || []).map((r) => <Row key={r.owner_id} r={r} />)}</div>
      </SheetContent>
    </Sheet>
  );
}
