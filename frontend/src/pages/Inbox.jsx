import { useEffect, useState, useMemo } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { MessagesSquare, Sparkles, Send, AlertOctagon, Inbox as InboxIcon, Calendar, Pill, FlaskConical, HelpCircle, Receipt, Info } from "lucide-react";

const CATEGORIES = [
  { key: "all", label: "All", icon: InboxIcon, cls: "border-slate-200 text-slate-700 bg-white" },
  { key: "urgent_review", label: "Urgent", icon: AlertOctagon, cls: "border-rose-300 text-rose-800 bg-rose-50" },
  { key: "appointment_needed", label: "Appointment", icon: Calendar, cls: "border-emerald-300 text-emerald-800 bg-emerald-50" },
  { key: "refill_request", label: "Refills", icon: Pill, cls: "border-sky-300 text-sky-800 bg-sky-50" },
  { key: "lab_follow_up", label: "Labs", icon: FlaskConical, cls: "border-purple-300 text-purple-800 bg-purple-50" },
  { key: "medication_question", label: "Meds Q", icon: HelpCircle, cls: "border-amber-300 text-amber-800 bg-amber-50" },
  { key: "billing", label: "Billing", icon: Receipt, cls: "border-slate-300 text-slate-800 bg-slate-50" },
  { key: "routine", label: "Routine", icon: Info, cls: "border-slate-200 text-slate-600 bg-slate-50" },
];

const CATEGORY_LABEL = Object.fromEntries(CATEGORIES.map((c) => [c.key, c.label]));
const CATEGORY_STYLE = Object.fromEntries(CATEGORIES.map((c) => [c.key, c.cls]));

const STATUS_LABEL = {
  new: "New",
  drafted: "Drafted",
  sent: "Sent",
  awaiting_reply: "Awaiting reply",
  booked: "Booked",
  paid: "Paid",
  closed: "Closed",
};

const STATUS_STYLE = {
  new: "border-slate-200 text-slate-700 bg-slate-50",
  drafted: "border-amber-200 text-amber-800 bg-amber-50",
  sent: "border-emerald-200 text-emerald-800 bg-emerald-50",
  awaiting_reply: "border-sky-200 text-sky-800 bg-sky-50",
  booked: "border-purple-200 text-purple-800 bg-purple-50",
  paid: "border-emerald-300 text-emerald-900 bg-emerald-100",
  closed: "border-slate-200 text-slate-500 bg-slate-50",
};

export default function Inbox() {
  const [msgs, setMsgs] = useState([]);
  const [sel, setSel] = useState(null);
  const [draft, setDraft] = useState(null);
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState("all");

  async function load() {
    const { data } = await api.get("/messages");
    setMsgs(data);
    // Use functional setter so we read the FRESH selection, not the closure snapshot.
    if (data.length) setSel((current) => current || data[0]);
  }

  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);
  useEffect(() => { setDraft(sel?.draft || null); }, [sel]);

  const counts = useMemo(() => {
    const c = { all: msgs.length };
    for (const cat of CATEGORIES) if (cat.key !== "all") c[cat.key] = 0;
    for (const m of msgs) if (m.category) c[m.category] = (c[m.category] || 0) + 1;
    return c;
  }, [msgs]);

  const filtered = filter === "all" ? msgs : msgs.filter((m) => m.category === filter);

  async function generate() {
    if (!sel) return;
    setBusy(true);
    try {
      const { data } = await api.post(`/messages/${sel.id}/draft`);
      setDraft(data);
      await load();
      toast.success(data.category === "urgent_review" ? "URGENT — review immediately." : "Draft ready — please review before sending.");
    } catch {
      toast.error("Draft generation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function approve() {
    if (!sel) return;
    try {
      await api.post(`/messages/${sel.id}/approve`);
      toast.success("Reply approved. Follow-up task queued if applicable.");
      await load();
      setSel((s) => (s ? { ...s, status: "sent" } : s));
    } catch {
      toast.error("Failed to approve.");
    }
  }

  async function setStatus(status) {
    if (!sel) return;
    try {
      await api.patch(`/messages/${sel.id}/status`, { status });
      toast.success(`Marked ${STATUS_LABEL[status]}.`);
      await load();
      setSel((s) => (s ? { ...s, status } : s));
    } catch {
      toast.error("Update failed.");
    }
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 lg:py-10 space-y-4">
      <div>
        <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Client inbox</div>
        <h1 className="font-serif-display text-3xl sm:text-4xl font-semibold text-emerald-950 tracking-tight mt-1">No message falls through the cracks.</h1>
      </div>

      {/* Category filter */}
      <div className="flex flex-wrap gap-2" data-testid="inbox-filters">
        {CATEGORIES.map((c) => (
          <button
            key={c.key}
            onClick={() => setFilter(c.key)}
            data-testid={`filter-${c.key}`}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-semibold transition-all ${filter === c.key ? c.cls + " shadow-sm" : "border-slate-200 text-slate-600 bg-white hover:bg-slate-50"}`}
          >
            <c.icon className="h-3 w-3" /> {c.label}
            {counts[c.key] > 0 && <span className={`ml-1 px-1.5 rounded-full text-[9px] ${filter === c.key ? "bg-white/50" : "bg-slate-100"}`}>{counts[c.key]}</span>}
          </button>
        ))}
      </div>

      <div className="grid lg:grid-cols-12 gap-6">
        <Card className="lg:col-span-4 p-3 rounded-2xl border-emerald-100 bg-white shadow-sm">
          <div className="text-xs uppercase tracking-widest text-slate-500 font-semibold px-3 pt-2 pb-3">{filtered.length} message{filtered.length !== 1 ? "s" : ""}</div>
          <div className="max-h-[70vh] overflow-y-auto">
            {filtered.map((m) => (
              <button
                key={m.id}
                onClick={() => setSel(m)}
                data-testid={`msg-${m.id}`}
                className={`w-full text-left p-3 rounded-xl mb-1 border transition-all ${sel?.id === m.id ? "bg-emerald-50 border-emerald-300" : "bg-white border-transparent hover:bg-slate-50"}`}
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="text-xs font-semibold text-slate-700 truncate">{m.owner?.name}</div>
                  <div className="text-[10px] text-slate-400 font-mono-clinical whitespace-nowrap">{new Date(m.received_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</div>
                </div>
                <div className="text-sm font-medium text-slate-900 truncate">{m.subject}</div>
                <div className="text-xs text-slate-500 truncate">{m.patient?.name} · {m.channel}</div>
                <div className="mt-1 flex items-center gap-1 flex-wrap">
                  {m.category && (
                    <Badge className={`text-[9px] border ${CATEGORY_STYLE[m.category] || CATEGORY_STYLE.routine}`}>{CATEGORY_LABEL[m.category] || m.category}</Badge>
                  )}
                  <Badge variant="outline" className={`text-[9px] border ${STATUS_STYLE[m.status] || STATUS_STYLE.new}`}>{STATUS_LABEL[m.status] || m.status}</Badge>
                </div>
              </button>
            ))}
            {filtered.length === 0 && (
              <div className="p-8 text-center text-slate-500 text-sm flex flex-col items-center gap-2">
                <InboxIcon className="h-6 w-6 text-slate-300" /> No messages in this filter
              </div>
            )}
          </div>
        </Card>

        <div className="lg:col-span-8 space-y-4">
          {sel ? (
            <>
              <Card className="p-5 rounded-2xl border-emerald-100 bg-white shadow-sm">
                <div className="flex items-start justify-between gap-3 flex-wrap">
                  <div className="min-w-0">
                    <div className="text-xs text-slate-500">From {sel.owner?.name} · {sel.channel} · {new Date(sel.received_at).toLocaleString()}</div>
                    <div className="font-serif-display text-xl font-semibold text-emerald-950 mt-1">{sel.subject}</div>
                    <div className="text-xs text-slate-500">Re: {sel.patient?.name} · {sel.patient?.breed}</div>
                    <div className="mt-2 flex items-center gap-1 flex-wrap">
                      {sel.category && (
                        <Badge className={`text-[10px] border ${CATEGORY_STYLE[sel.category] || CATEGORY_STYLE.routine}`}>{CATEGORY_LABEL[sel.category] || sel.category}</Badge>
                      )}
                      <Badge variant="outline" className={`text-[10px] border ${STATUS_STYLE[sel.status] || STATUS_STYLE.new}`}>{STATUS_LABEL[sel.status] || sel.status}</Badge>
                    </div>
                  </div>
                  <Button onClick={generate} disabled={busy} data-testid="inbox-generate-draft" className="bg-emerald-700 hover:bg-emerald-800 text-white rounded-full">
                    <Sparkles className="h-4 w-4 mr-2" /> {busy ? "Drafting…" : "AI classify & draft"}
                  </Button>
                </div>
                <div className="mt-4 p-4 rounded-xl bg-slate-50 border border-slate-100 text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">
                  {sel.body}
                </div>

                {/* Status pipeline */}
                <div className="mt-4 flex flex-wrap gap-1.5">
                  {["sent", "awaiting_reply", "booked", "paid", "closed"].map((s) => (
                    <Button
                      key={s}
                      onClick={() => setStatus(s)}
                      size="sm"
                      variant={sel.status === s ? "default" : "outline"}
                      data-testid={`status-${s}`}
                      className={`h-7 rounded-full text-[11px] ${sel.status === s ? "bg-emerald-700 hover:bg-emerald-800 text-white" : "border-slate-200 text-slate-600 hover:bg-slate-50"}`}
                    >
                      {STATUS_LABEL[s]}
                    </Button>
                  ))}
                </div>
              </Card>

              {draft && (
                <Card className="p-5 rounded-2xl border-emerald-100 bg-white shadow-sm">
                  <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Sparkles className="h-4 w-4 text-emerald-700" />
                      <div className="text-xs uppercase tracking-widest text-slate-500 font-semibold">Draft reply</div>
                      {draft.category && (
                        <Badge className={`text-[10px] border ${CATEGORY_STYLE[draft.category] || CATEGORY_STYLE.routine}`}>
                          {draft.category === "urgent_review" && <AlertOctagon className="h-3 w-3 mr-1" />}
                          {CATEGORY_LABEL[draft.category] || draft.category}
                        </Badge>
                      )}
                    </div>
                    <Button onClick={approve} data-testid="inbox-approve" variant="outline" className="border-emerald-300 text-emerald-800 hover:bg-emerald-50 rounded-full">
                      <Send className="h-4 w-4 mr-2" /> Approve &amp; send
                    </Button>
                  </div>
                  {draft.one_line_summary && <div className="text-xs text-slate-500 mb-2 italic">{draft.one_line_summary}</div>}
                  <Textarea
                    value={draft.draft_reply || ""}
                    onChange={(e) => setDraft({ ...draft, draft_reply: e.target.value })}
                    rows={9}
                    className="resize-none"
                    data-testid="inbox-draft-text"
                  />
                  {draft.internal_note && (
                    <div className="mt-3 p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-xs">
                      <span className="font-semibold uppercase tracking-widest text-[9px]">Staff note · </span>{draft.internal_note}
                    </div>
                  )}
                  {draft.suggests_task && (
                    <div className="mt-2 p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs">
                      <span className="font-semibold uppercase tracking-widest text-[9px]">Suggested follow-up · </span>{draft.suggests_task}
                      <div className="text-[10px] text-emerald-700 mt-1">A task is created automatically when you approve.</div>
                    </div>
                  )}
                </Card>
              )}
            </>
          ) : (
            <Card className="p-10 rounded-2xl border-emerald-100 bg-white text-center text-slate-500">
              <MessagesSquare className="h-8 w-8 text-slate-300 mx-auto mb-2" /> Select a message to classify and draft a reply.
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
