import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { PhoneCall, MessageSquare, Sparkles, Trash2, AlertTriangle, ShieldCheck, ArrowRight } from "lucide-react";
import { toast } from "sonner";

export default function PhoneSms() {
  const [status, setStatus] = useState(null);
  const [usage, setUsage] = useState(null);
  const [overage, setOverage] = useState(null);
  const [areaCode, setAreaCode] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      const [s, u, o] = await Promise.all([
        api.get("/twilio/status"),
        api.get("/voice/usage-summary"),
        api.get("/billing-cycle/preview"),
      ]);
      setStatus(s.data);
      setUsage(u.data);
      setOverage(o.data);
    } catch (err) {
      console.warn("Phone/SMS load failed:", err);
    }
  }
  useEffect(() => { load(); }, []);

  async function provision() {
    setBusy(true);
    try {
      const { data } = await api.post("/twilio/provision", { area_code: areaCode || null });
      toast.success(`Provisioned ${data.phone_number}`);
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to provision number");
    } finally { setBusy(false); }
  }

  async function release() {
    if (!confirm("Release this Twilio number? Inbound calls will stop routing to Vetaura.")) return;
    setBusy(true);
    try {
      await api.post("/twilio/release", { phone_sid: status.number.phone_sid });
      toast.success("Number released");
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Release failed");
    } finally { setBusy(false); }
  }

  const capPct = usage?.voice_minutes_used_pct || 0;
  const overageDollars = usage ? (usage.overage_cost_cents / 100).toFixed(2) : "0.00";
  const connected = status?.connected;

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-6 lg:py-10 space-y-6">
      <div>
        <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Receptionist · Phone &amp; SMS</div>
        <h1 className="font-serif-display text-3xl sm:text-4xl font-semibold text-emerald-950 tracking-tight mt-1">Answer every call. Return every text.</h1>
        <p className="text-sm text-slate-600 mt-2 max-w-2xl">Vetaura orchestrates calls and SMS through <strong>your</strong> Twilio account. Connect it once, complete A2P registration inside your Twilio Console, then provision a number here — the webhook URLs are auto-configured.</p>
      </div>

      {!connected && (
        <Card className="p-5 rounded-2xl border-amber-200 bg-amber-50/60 shadow-sm" data-testid="phone-not-connected">
          <div className="flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 text-amber-700 mt-0.5" />
            <div className="flex-1">
              <div className="font-semibold text-amber-900">Connect your Twilio account to enable phone &amp; SMS</div>
              <div className="text-sm text-amber-800 mt-1">Vetaura is a pure orchestrator — your clinic owns the Twilio account, phone numbers, and A2P Brand/Campaign registration. We only need a Restricted API Key you control.</div>
              <div className="mt-3 flex gap-2">
                <Link to="/app/integrations"><Button className="rounded-full bg-emerald-700 hover:bg-emerald-800 text-white h-9"><PhoneCall className="h-3.5 w-3.5 mr-1.5" /> Connect Twilio</Button></Link>
                <Link to="/app/compliance"><Button variant="outline" className="rounded-full border-emerald-200 text-emerald-800 h-9"><ShieldCheck className="h-3.5 w-3.5 mr-1.5" /> Open compliance checklist</Button></Link>
              </div>
            </div>
          </div>
        </Card>
      )}

      <div className="grid md:grid-cols-2 gap-4">
        <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm" data-testid="twilio-number-card">
          <div className="flex items-center gap-2 mb-3">
            <PhoneCall className="h-4 w-4 text-emerald-700" />
            <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Clinic number</div>
          </div>
          {status?.number ? (
            <div>
              <div className="font-mono-clinical text-2xl text-emerald-950">{status.number.phone_number}</div>
              <div className="text-xs text-slate-500 mt-1">{status.number.friendly_name}</div>
              {status.messaging_service_sid ? (
                <Badge variant="outline" className="mt-2 text-[10px] border-emerald-200 text-emerald-800 bg-emerald-50">Attached to Messaging Service · {status.messaging_service_sid.slice(0, 10)}…</Badge>
              ) : (
                <Badge variant="outline" className="mt-2 text-[10px] border-amber-200 text-amber-800 bg-amber-50">Attach this number to your Messaging Service in Twilio Console</Badge>
              )}
              <div className="mt-4 flex gap-2">
                <Button variant="outline" onClick={release} disabled={busy} className="rounded-full border-rose-200 text-rose-700 hover:bg-rose-50" data-testid="twilio-release-btn">
                  <Trash2 className="h-3.5 w-3.5 mr-2" /> Release number
                </Button>
              </div>
            </div>
          ) : (
            <div>
              <p className="text-sm text-slate-600">No number yet. Provision one from your own Twilio account below — Vetaura will auto-configure the voice + SMS webhooks.</p>
              <div className="mt-4 grid grid-cols-[1fr_auto] gap-2">
                <Input value={areaCode} onChange={(e) => setAreaCode(e.target.value)} placeholder="Preferred area code (e.g. 415)" data-testid="twilio-area-input" />
                <Button onClick={provision} disabled={busy || !connected} data-testid="twilio-provision-btn" className="rounded-full bg-emerald-700 hover:bg-emerald-800 text-white">
                  <Sparkles className="h-4 w-4 mr-2" /> {busy ? "Provisioning…" : "Provision"}
                </Button>
              </div>
              {!connected && <div className="text-[11px] text-amber-700 mt-2">Connect Twilio first.</div>}
            </div>
          )}
        </Card>

        <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm" data-testid="voice-usage-card">
          <div className="flex items-center gap-2 mb-3">
            <MessageSquare className="h-4 w-4 text-emerald-700" />
            <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Usage · this month</div>
          </div>
          <div className="text-3xl font-serif-display text-emerald-950">
            {usage?.voice_minutes ?? 0}<span className="text-sm text-slate-500 font-sans"> / {usage?.voice_minutes_cap ?? 0} min</span>
          </div>
          <div className="h-2 rounded-full bg-slate-100 mt-3 overflow-hidden">
            <div className="h-full bg-emerald-600 rounded-full transition-all" style={{ width: `${Math.min(100, capPct)}%` }} />
          </div>
          <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
            <div>
              <div className="text-[10px] uppercase tracking-widest text-slate-500 font-semibold">SMS handled</div>
              <div className="font-mono-clinical text-lg text-slate-800">{usage?.sms_count ?? 0}</div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-widest text-slate-500 font-semibold">Overage</div>
              <div className="font-mono-clinical text-lg text-slate-800">${overageDollars}</div>
            </div>
          </div>
          <div className="text-[11px] text-slate-500 mt-3">Overage is metered at $0.35/min and auto-billed via Stripe at cycle close.</div>
          {overage?.overage_minutes > 0 && (
            <div className="mt-3 text-[11px] text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-2 py-1.5">Projected overage this cycle: <strong>{overage.overage_minutes} min · ${(overage.overage_minutes * 0.35).toFixed(2)}</strong></div>
          )}
          <Badge variant="outline" className="mt-3 border-emerald-200 text-emerald-800 bg-emerald-50 text-[10px]">Plan: {usage?.plan || "—"}</Badge>
        </Card>
      </div>

      <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm" data-testid="phone-how-card">
        <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold mb-2">How it works</div>
        <ol className="text-sm text-slate-700 space-y-1.5 list-decimal list-inside">
          <li>Inbound call rings your Twilio number → Vetaura answers with your greeting.</li>
          <li>Caller speaks → Twilio speech recognition → Claude Sonnet 5 replies via TwiML voice.</li>
          <li>No response or after hours → voicemail is recorded, transcribed by Whisper, and turned into a task in your Inbox.</li>
          <li>Emergency keywords ("collapse", "seizure"…) trigger an immediate deterministic handoff to your emergency line.</li>
          <li>Inbound SMS: STOP / HELP / START are handled automatically; other messages get an AI reply. Every send is checked against your consent ledger.</li>
        </ol>
        <div className="mt-3">
          <Link to="/app/compliance" className="text-xs text-emerald-700 hover:underline inline-flex items-center gap-1">Open the SMS compliance ledger <ArrowRight className="h-3 w-3" /></Link>
        </div>
      </Card>
    </div>
  );
}
