import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { PhoneCall, MessageSquare, Sparkles, Trash2, AlertTriangle } from "lucide-react";
import { toast } from "sonner";

export default function PhoneSms() {
  const [status, setStatus] = useState(null);
  const [usage, setUsage] = useState(null);
  const [areaCode, setAreaCode] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      const [s, u] = await Promise.all([api.get("/twilio/status"), api.get("/voice/usage-summary")]);
      setStatus(s.data);
      setUsage(u.data);
    } catch (e) {
      // ignore
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
  const configured = status?.configured;

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-6 lg:py-10 space-y-6">
      <div>
        <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Receptionist · Phone & SMS</div>
        <h1 className="font-serif-display text-3xl sm:text-4xl font-semibold text-emerald-950 tracking-tight mt-1">Answer every call. Return every text.</h1>
        <p className="text-sm text-slate-600 mt-2 max-w-2xl">Provision a dedicated Twilio phone number and Vetaura will answer inbound calls with your receptionist voice, transcribe voicemails with Whisper, and reply to SMS on your clinic's behalf. Everything is metered against your plan's voice minutes.</p>
      </div>

      {!configured && (
        <Card className="p-5 rounded-2xl border-amber-200 bg-amber-50/60 shadow-sm" data-testid="twilio-not-configured">
          <div className="flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 text-amber-700 mt-0.5" />
            <div>
              <div className="font-semibold text-amber-900">Twilio not configured on this instance yet</div>
              <div className="text-sm text-amber-800 mt-1">Ask your Vetaura admin to add <code>TWILIO_ACCOUNT_SID</code> and <code>TWILIO_AUTH_TOKEN</code> to the backend environment. Once set, you can provision a dedicated phone number here in about 30 seconds.</div>
              <div className="text-xs text-amber-700/80 mt-3 font-mono-clinical">Get them at https://console.twilio.com → Account → API keys &amp; tokens</div>
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
              <div className="mt-4 flex gap-2">
                <Button variant="outline" onClick={release} disabled={busy} className="rounded-full border-rose-200 text-rose-700 hover:bg-rose-50" data-testid="twilio-release-btn">
                  <Trash2 className="h-3.5 w-3.5 mr-2" /> Release number
                </Button>
              </div>
            </div>
          ) : (
            <div>
              <p className="text-sm text-slate-600">No number yet. Provision one below and we'll wire the voice & SMS webhooks automatically.</p>
              <div className="mt-4 grid grid-cols-[1fr_auto] gap-2">
                <Input value={areaCode} onChange={(e) => setAreaCode(e.target.value)} placeholder="Preferred area code (e.g. 415)" data-testid="twilio-area-input" />
                <Button onClick={provision} disabled={busy || !configured} data-testid="twilio-provision-btn" className="rounded-full bg-emerald-700 hover:bg-emerald-800 text-white">
                  <Sparkles className="h-4 w-4 mr-2" /> {busy ? "Provisioning…" : "Provision"}
                </Button>
              </div>
              {!configured && <div className="text-[11px] text-amber-700 mt-2">Provisioning is disabled until Twilio credentials are set on the server.</div>}
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
          <li>Inbound SMS follows the same brain and replies in a text thread.</li>
        </ol>
      </Card>
    </div>
  );
}
