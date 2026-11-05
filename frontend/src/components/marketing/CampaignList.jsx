import { useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { CheckCircle2, XCircle, Clock, Smartphone, BarChart3 } from "lucide-react";
import { CampaignResultsSheet } from "./CampaignResultsSheet";
import { toast } from "sonner";
import { errMsg } from "./TemplateManager";

const STATUS = {
  pending_approval: ["Awaiting approval", "bg-amber-100 text-amber-800 border-amber-200"],
  scheduled: ["Queued for quiet-hours end", "bg-sky-100 text-sky-800 border-sky-200"],
  sending: ["Sending", "bg-emerald-100 text-emerald-800 border-emerald-200"],
  completed: ["Completed", "bg-emerald-100 text-emerald-800 border-emerald-200"],
  rejected: ["Rejected", "bg-rose-100 text-rose-800 border-rose-200"],
  cancelled: ["Cancelled", "bg-slate-100 text-slate-600 border-slate-200"],
};

function Actions({ c, me, isOwner, soloOwner, act, openResults }) {
  const pending = c.status === "pending_approval";
  const canApprove = pending && isOwner && (c.created_by !== me || soloOwner);
  return (
    <div className="flex flex-wrap gap-2">
      {canApprove && <Button size="sm" onClick={() => act(c.id, "approve")} data-testid={`campaign-approve-${c.id}`} className="h-8 rounded-full bg-emerald-700 hover:bg-emerald-800 text-white text-xs"><CheckCircle2 className="h-3.5 w-3.5 mr-1" /> Approve & send</Button>}
      {pending && isOwner && <Button size="sm" variant="outline" onClick={() => act(c.id, "reject")} data-testid={`campaign-reject-${c.id}`} className="h-8 rounded-full border-rose-200 text-rose-700 text-xs"><XCircle className="h-3.5 w-3.5 mr-1" /> Reject</Button>}
      {(pending || c.status === "scheduled") && (c.created_by === me || isOwner) && <Button size="sm" variant="ghost" onClick={() => act(c.id, "cancel")} data-testid={`campaign-cancel-${c.id}`} className="h-8 text-xs text-slate-500">Cancel</Button>}
      {pending && isOwner && <Button size="sm" variant="outline" onClick={() => act(c.id, "test")} data-testid={`campaign-test-${c.id}`} className="h-8 rounded-full border-emerald-300 text-emerald-800 text-xs"><Smartphone className="h-3.5 w-3.5 mr-1" /> Send test to my phone</Button>}
      {["completed", "sending"].includes(c.status) && <Button size="sm" variant="outline" onClick={() => openResults(c.id)} data-testid={`campaign-results-${c.id}`} className="h-8 rounded-full border-emerald-300 text-emerald-800 text-xs"><BarChart3 className="h-3.5 w-3.5 mr-1" /> Results</Button>}
      {pending && c.created_by === me && !soloOwner && <span className="text-xs text-slate-500 self-center" data-testid={`campaign-needs-other-${c.id}`}>Another owner must approve</span>}
    </div>
  );
}

export function CampaignList({ campaigns, me, isOwner, soloOwner = false, onChange }) {
  const [showAll, setShowAll] = useState(false);
  const [resultsId, setResultsId] = useState(null);
  const shown = showAll ? campaigns : campaigns.slice(0, 10);
  async function act(id, action) {
    if (action === "approve" && !window.confirm("Send this blast to every client with marketing consent?")) return;
    const body = action === "reject" ? { reason: window.prompt("Reason for rejecting (optional)") || "" } : undefined;
    try {
      const { data } = await api.post(`/sms/marketing/campaigns/${id}/${action}`, body);
      if (action === "test") toast.success(`Test sent to ${data.to}.`);
      if (action === "approve") toast.success(data.status === "scheduled" ? "Approved — queued until quiet hours end." : "Approved — sending now.");
      onChange();
    } catch (e) { toast.error(errMsg(e, "Action failed.")); if (action === "test") onChange(); }
  }

  return (
    <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm" data-testid="campaigns-card">
      <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold mb-3">Blasts</div>
      {campaigns.length === 0 && <div className="text-sm text-slate-500 py-4" data-testid="campaigns-empty">No blasts yet.</div>}
      {shown.map((c) => {
        const [label, cls] = STATUS[c.status] || [c.status, ""];
        return (
          <div key={c.id} className="py-4 border-t border-slate-100 first:border-t-0 space-y-2" data-testid={`campaign-${c.id}`}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="font-semibold text-emerald-950">{c.name}</div>
              <Badge variant="outline" className={`text-[10px] ${cls}`} data-testid={`campaign-status-${c.id}`}>{label}</Badge>
            </div>
            <div className="text-xs text-slate-500">{c.recipient_count} recipient{c.recipient_count === 1 ? "" : "s"} · {c.template_name} · by {c.created_by}{c.approved_by ? ` · approved by ${c.approved_by}` : ""}</div>
            {c.status === "scheduled" && c.scheduled_for && <div className="text-xs text-sky-800 flex items-center gap-1"><Clock className="h-3 w-3" /> Sends after {new Date(c.scheduled_for).toLocaleString()}</div>}
            {c.results && <div className="text-xs text-slate-600" data-testid={`campaign-results-summary-${c.id}`}>{c.results.sent} sent · {c.results.blocked} blocked · {c.results.failed} failed</div>}
            {c.reject_reason && <div className="text-xs text-rose-700">Reason: {c.reject_reason}</div>}
            {(c.tests || []).length > 0 && <div className="text-xs text-slate-500" data-testid={`campaign-tests-${c.id}`}>{c.tests.length} test attempt{c.tests.length > 1 ? "s" : ""} · last {c.tests[c.tests.length - 1].status === "sent" ? "delivered to Twilio" : "failed"} ({c.tests[c.tests.length - 1].to})</div>}
            <Actions c={c} me={me} isOwner={isOwner} soloOwner={soloOwner} act={act} openResults={setResultsId} />
          </div>
        );
      })}
      {campaigns.length > 10 && (
        <Button variant="ghost" size="sm" onClick={() => setShowAll((v) => !v)} data-testid="campaigns-toggle-all" className="mt-2 text-xs text-emerald-800">
          {showAll ? "Show recent only" : `Show all ${campaigns.length} blasts`}
        </Button>
      )}
      <CampaignResultsSheet campaignId={resultsId} onClose={() => setResultsId(null)} />
    </Card>
  );
}
