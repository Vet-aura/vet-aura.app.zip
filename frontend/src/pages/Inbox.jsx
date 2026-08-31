import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { MessagesSquare, Sparkles, Send, AlertOctagon, Inbox as InboxIcon } from "lucide-react";

const urgencyStyle = {
  urgent: "bg-rose-50 border-rose-200 text-rose-800",
  routine: "bg-emerald-50 border-emerald-200 text-emerald-800",
  refill: "bg-sky-50 border-sky-200 text-sky-800",
  post_op: "bg-amber-50 border-amber-200 text-amber-800",
  scheduling: "bg-purple-50 border-purple-200 text-purple-800",
};

export default function Inbox() {
  const [msgs, setMsgs] = useState([]);
  const [sel, setSel] = useState(null);
  const [draft, setDraft] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/messages").then((r) => {
      setMsgs(r.data);
      if (r.data.length) setSel(r.data[0]);
    });
  }, []);

  useEffect(() => {
    setDraft(sel?.draft || null);
  }, [sel]);

  async function generate() {
    if (!sel) return;
    setBusy(true);
    try {
      const { data } = await api.post(`/messages/${sel.id}/draft`);
      setDraft(data);
      toast.success("Draft ready — please review before sending.");
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
      toast.success("Reply approved and sent (mock).");
      setMsgs((prev) => prev.map((m) => (m.id === sel.id ? { ...m, status: "sent" } : m)));
    } catch {
      toast.error("Failed to approve.");
    }
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 lg:py-10 space-y-6">
      <div>
        <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Client inbox</div>
        <h1 className="font-serif-display text-3xl sm:text-4xl font-semibold text-emerald-950 tracking-tight mt-1">Empathetic replies, in seconds.</h1>
      </div>

      <div className="grid lg:grid-cols-12 gap-6">
        <Card className="lg:col-span-4 p-3 rounded-2xl border-emerald-100 bg-white shadow-sm">
          <div className="text-xs uppercase tracking-widest text-slate-500 font-semibold px-3 pt-2 pb-3">Messages</div>
          <div className="max-h-[70vh] overflow-y-auto">
            {msgs.map((m) => (
              <button
                key={m.id}
                onClick={() => setSel(m)}
                data-testid={`msg-${m.id}`}
                className={`w-full text-left p-3 rounded-xl mb-1 border transition-all ${sel?.id === m.id ? "bg-emerald-50 border-emerald-300" : "bg-white border-transparent hover:bg-slate-50"}`}
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="text-xs font-semibold text-slate-700">{m.owner?.name}</div>
                  <div className="text-[10px] text-slate-400 font-mono-clinical">{new Date(m.received_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</div>
                </div>
                <div className="text-sm font-medium text-slate-900 truncate">{m.subject}</div>
                <div className="text-xs text-slate-500 truncate">{m.patient?.name} · {m.channel}</div>
                {m.status === "sent" && <Badge variant="outline" className="mt-1 text-[9px] border-emerald-200 text-emerald-800 bg-emerald-50">Sent</Badge>}
              </button>
            ))}
            {msgs.length === 0 && (
              <div className="p-8 text-center text-slate-500 text-sm flex flex-col items-center gap-2">
                <InboxIcon className="h-6 w-6 text-slate-300" /> Inbox empty
              </div>
            )}
          </div>
        </Card>

        <div className="lg:col-span-8 space-y-4">
          {sel ? (
            <>
              <Card className="p-5 rounded-2xl border-emerald-100 bg-white shadow-sm">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-xs text-slate-500">From {sel.owner?.name} · {sel.channel} · {new Date(sel.received_at).toLocaleString()}</div>
                    <div className="font-serif-display text-xl font-semibold text-emerald-950 mt-1">{sel.subject}</div>
                    <div className="text-xs text-slate-500">Re: {sel.patient?.name} · {sel.patient?.breed}</div>
                  </div>
                  <Button onClick={generate} disabled={busy} data-testid="inbox-generate-draft" className="bg-emerald-700 hover:bg-emerald-800 text-white rounded-full">
                    <Sparkles className="h-4 w-4 mr-2" /> {busy ? "Drafting…" : "AI draft"}
                  </Button>
                </div>
                <div className="mt-4 p-4 rounded-xl bg-slate-50 border border-slate-100 text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">
                  {sel.body}
                </div>
              </Card>

              {draft && (
                <Card className="p-5 rounded-2xl border-emerald-100 bg-white shadow-sm">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <Sparkles className="h-4 w-4 text-emerald-700" />
                      <div className="text-xs uppercase tracking-widest text-slate-500 font-semibold">Draft reply</div>
                      {draft.urgency && (
                        <Badge className={`text-[10px] border ${urgencyStyle[draft.urgency] || "bg-slate-50 border-slate-200 text-slate-700"}`}>
                          {draft.urgency === "urgent" && <AlertOctagon className="h-3 w-3 mr-1" />}
                          {draft.urgency}
                        </Badge>
                      )}
                    </div>
                    <Button onClick={approve} data-testid="inbox-approve" variant="outline" className="border-emerald-300 text-emerald-800 hover:bg-emerald-50 rounded-full">
                      <Send className="h-4 w-4 mr-2" /> Approve & send
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
                </Card>
              )}
            </>
          ) : (
            <Card className="p-10 rounded-2xl border-emerald-100 bg-white text-center text-slate-500">
              <MessagesSquare className="h-8 w-8 text-slate-300 mx-auto mb-2" /> Select a message to draft a reply.
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
