import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PhoneCall, Mail, RotateCcw, Trash2, ShieldCheck, KeyRound, Copy, ExternalLink, Info, Sparkles } from "lucide-react";
import { toast } from "sonner";

const TWILIO_HELP = [
  { step: "1", label: "Create a Twilio account and add a payment method", href: "https://www.twilio.com/try-twilio" },
  { step: "2", label: "Purchase (or port) a U.S. 10-digit long code phone number", href: "https://console.twilio.com/us1/develop/phone-numbers/manage/incoming" },
  { step: "3", label: "Create a Messaging Service and attach your number", href: "https://console.twilio.com/us1/develop/sms/services" },
  { step: "4", label: "Register your Brand and Campaign for A2P 10DLC (Customer Care)", href: "https://console.twilio.com/us1/develop/sms/regulatory-compliance/brands" },
  { step: "5", label: "Create a RESTRICTED API key (not the Auth Token) and paste it below", href: "https://console.twilio.com/us1/account/keys-credentials/api-keys" },
];

export default function Integrations() {
  const [tw, setTw] = useState(null);
  const [em, setEm] = useState(null);
  const [twForm, setTwForm] = useState({ account_sid: "", api_key_sid: "", api_key_secret: "", messaging_service_sid: "" });
  const [emForm, setEmForm] = useState({ provider: "resend", api_key: "", from_email: "", from_name: "" });
  const [busy, setBusy] = useState(null);

  async function load() {
    try {
      const [t, e] = await Promise.all([api.get("/integrations/twilio"), api.get("/integrations/email")]);
      setTw(t.data); setEm(e.data);
    } catch (err) { console.warn("Integrations load failed:", err); }
  }
  useEffect(() => { load(); }, []);

  async function saveTwilio() {
    if (!twForm.account_sid.startsWith("AC") || !twForm.api_key_sid.startsWith("SK") || twForm.api_key_secret.length < 8) {
      return toast.info("Enter your Account SID (AC…), API Key SID (SK…), and API Key Secret.");
    }
    setBusy("twilio");
    try {
      const { data } = await api.post("/integrations/twilio", twForm);
      toast.success(`Connected to ${data.friendly_name}`);
      setTwForm({ account_sid: "", api_key_sid: "", api_key_secret: "", messaging_service_sid: "" });
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not connect Twilio.");
    } finally { setBusy(null); }
  }
  async function disconnectTwilio() {
    if (!confirm("Disconnect Twilio? Inbound calls and SMS will stop.")) return;
    await api.delete("/integrations/twilio").catch(() => {});
    toast.success("Twilio disconnected");
    await load();
  }
  async function rotateWebhookToken() {
    setBusy("rotate");
    try {
      await api.post("/integrations/twilio/rotate-webhook-token");
      toast.success("Webhook URLs rotated. Update Twilio Console with the new URLs.");
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Rotation failed.");
    } finally { setBusy(null); }
  }

  async function saveEmail() {
    if (!emForm.api_key || !emForm.from_email) return toast.info("Provider API key and from-email are required.");
    setBusy("email");
    try {
      await api.post("/integrations/email", emForm);
      toast.success(`Connected ${emForm.provider}`);
      setEmForm({ ...emForm, api_key: "" });
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not connect email provider.");
    } finally { setBusy(null); }
  }
  async function disconnectEmail() {
    if (!confirm("Disconnect email provider? Outbound emails will stop.")) return;
    await api.delete("/integrations/email").catch(() => {});
    toast.success("Email disconnected");
    await load();
  }

  const copy = (t) => { navigator.clipboard.writeText(t); toast.success("Copied"); };

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-6 lg:py-10 space-y-6">
      <div>
        <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Integrations · Your accounts, your keys</div>
        <h1 className="font-serif-display text-3xl sm:text-4xl font-semibold text-emerald-950 tracking-tight mt-1">Bring your own Twilio &amp; email.</h1>
        <p className="text-sm text-slate-600 mt-2 max-w-2xl">Your clinic owns the messaging accounts, phone numbers, deliverability reputation, and A2P registration. Vetaura simply orchestrates through restricted credentials you can revoke at any time.</p>
      </div>

      {/* Twilio */}
      <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm" data-testid="integrations-twilio-card">
        <div className="flex items-center justify-between gap-3 mb-4">
          <div className="flex items-center gap-2">
            <PhoneCall className="h-4 w-4 text-emerald-700" />
            <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Twilio</div>
          </div>
          {tw?.connected ? (
            <Badge variant="outline" className="border-emerald-200 text-emerald-800 bg-emerald-50 text-[10px]">Connected · {tw.friendly_name}</Badge>
          ) : (
            <Badge variant="outline" className="border-slate-200 text-slate-500 bg-slate-50 text-[10px]">Not connected</Badge>
          )}
        </div>

        {!tw?.connected ? (
          <>
            <div className="mb-5 grid sm:grid-cols-2 gap-2">
              {TWILIO_HELP.map((s) => (
                <a key={s.step} href={s.href} target="_blank" rel="noreferrer" className="flex items-start gap-2 text-xs text-slate-700 hover:text-emerald-800 border border-emerald-100 rounded-xl p-3 bg-emerald-50/30">
                  <span className="font-serif-display text-lg text-emerald-800 leading-none">{s.step}</span>
                  <span>{s.label} <ExternalLink className="inline h-3 w-3 ml-1 opacity-60" /></span>
                </a>
              ))}
            </div>
            <div className="grid sm:grid-cols-2 gap-3">
              <label className="text-xs text-slate-600">Account SID
                <Input value={twForm.account_sid} onChange={(e) => setTwForm({ ...twForm, account_sid: e.target.value.trim() })} placeholder="AC••••••••••••••••••••••••••••••••" data-testid="tw-account-sid" />
              </label>
              <label className="text-xs text-slate-600">API Key SID
                <Input value={twForm.api_key_sid} onChange={(e) => setTwForm({ ...twForm, api_key_sid: e.target.value.trim() })} placeholder="SK••••••••••••••••••••••••••••••••" data-testid="tw-api-key-sid" />
              </label>
              <label className="text-xs text-slate-600">API Key Secret
                <Input type="password" value={twForm.api_key_secret} onChange={(e) => setTwForm({ ...twForm, api_key_secret: e.target.value })} placeholder="••••••••••••••••••••••••" data-testid="tw-api-key-secret" />
              </label>
              <label className="text-xs text-slate-600">Messaging Service SID (recommended)
                <Input value={twForm.messaging_service_sid} onChange={(e) => setTwForm({ ...twForm, messaging_service_sid: e.target.value.trim() })} placeholder="MG•••••••••••••••••••••••••••" data-testid="tw-msg-svc-sid" />
              </label>
            </div>
            <div className="mt-4 flex items-center gap-2">
              <Button onClick={saveTwilio} disabled={busy === "twilio"} data-testid="tw-connect-btn" className="rounded-full bg-emerald-700 hover:bg-emerald-800 text-white">
                <KeyRound className="h-4 w-4 mr-2" /> {busy === "twilio" ? "Verifying…" : "Connect Twilio"}
              </Button>
              <span className="text-[11px] text-slate-500 inline-flex items-center gap-1"><Info className="h-3 w-3" /> Never share your Twilio Auth Token. We only accept a Restricted API Key.</span>
            </div>
          </>
        ) : (
          <div className="space-y-4">
            <div className="grid sm:grid-cols-2 gap-3 text-sm">
              <div><span className="text-slate-500 text-xs">Account SID</span><div className="font-mono-clinical">{tw.account_sid_masked}</div></div>
              <div><span className="text-slate-500 text-xs">API Key SID</span><div className="font-mono-clinical">{tw.api_key_sid_masked}</div></div>
              <div><span className="text-slate-500 text-xs">Messaging Service SID</span><div className="font-mono-clinical">{tw.messaging_service_sid || <span className="text-amber-700">Not connected · set one so SMS flows through your approved campaign</span>}</div></div>
              <div><span className="text-slate-500 text-xs">Last verified</span><div className="font-mono-clinical text-slate-800">{tw.verified_at?.slice(0, 19).replace("T", " ")}Z</div></div>
            </div>
            {tw.webhooks && (
              <div className="rounded-xl border border-emerald-100 bg-emerald-50/40 p-3 space-y-2 text-xs" data-testid="tw-webhooks">
                <div className="text-[11px] uppercase tracking-widest text-emerald-700 font-semibold">Paste these into your Twilio number config</div>
                {[
                  ["Voice URL", tw.webhooks.voice_url],
                  ["Voice status callback", tw.webhooks.voice_status_callback],
                  ["Messaging URL", tw.webhooks.sms_url],
                ].map(([label, url]) => (
                  <div key={label} className="grid grid-cols-[140px_1fr_auto] gap-2 items-center">
                    <div className="text-slate-500">{label}</div>
                    <div className="font-mono-clinical truncate text-slate-800">{url}</div>
                    <Button size="sm" variant="ghost" onClick={() => copy(url)} className="h-7 w-7 p-0"><Copy className="h-3 w-3" /></Button>
                  </div>
                ))}
              </div>
            )}
            <div className="flex gap-2">
              <Button variant="outline" onClick={rotateWebhookToken} disabled={busy === "rotate"} data-testid="tw-rotate-btn" className="rounded-full border-emerald-200 text-emerald-800 hover:bg-emerald-50 text-xs">
                <RotateCcw className="h-3 w-3 mr-1.5" /> Rotate webhook token
              </Button>
              <Button variant="outline" onClick={disconnectTwilio} data-testid="tw-disconnect-btn" className="rounded-full border-rose-200 text-rose-700 hover:bg-rose-50 text-xs">
                <Trash2 className="h-3 w-3 mr-1.5" /> Disconnect
              </Button>
            </div>
          </div>
        )}
      </Card>

      {/* Email */}
      <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm" data-testid="integrations-email-card">
        <div className="flex items-center justify-between gap-3 mb-4">
          <div className="flex items-center gap-2">
            <Mail className="h-4 w-4 text-emerald-700" />
            <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Email delivery</div>
          </div>
          {em?.connected ? (
            <Badge variant="outline" className="border-emerald-200 text-emerald-800 bg-emerald-50 text-[10px]">Connected · {em.provider}</Badge>
          ) : (
            <Badge variant="outline" className="border-slate-200 text-slate-500 bg-slate-50 text-[10px]">Not connected</Badge>
          )}
        </div>

        {!em?.connected ? (
          <div className="space-y-3">
            <div className="grid sm:grid-cols-2 gap-3">
              <label className="text-xs text-slate-600">Provider
                <Select value={emForm.provider} onValueChange={(v) => setEmForm({ ...emForm, provider: v })}>
                  <SelectTrigger data-testid="em-provider"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="resend">Resend (recommended)</SelectItem>
                    <SelectItem value="sendgrid">SendGrid</SelectItem>
                  </SelectContent>
                </Select>
              </label>
              <label className="text-xs text-slate-600">API key
                <Input type="password" value={emForm.api_key} onChange={(e) => setEmForm({ ...emForm, api_key: e.target.value })} placeholder="re_•••• / SG.••••" data-testid="em-api-key" />
              </label>
              <label className="text-xs text-slate-600">From email
                <Input type="email" value={emForm.from_email} onChange={(e) => setEmForm({ ...emForm, from_email: e.target.value.trim() })} placeholder="care@your-clinic.com" data-testid="em-from-email" />
              </label>
              <label className="text-xs text-slate-600">From name
                <Input value={emForm.from_name} onChange={(e) => setEmForm({ ...emForm, from_name: e.target.value })} placeholder="Your Clinic Name" data-testid="em-from-name" />
              </label>
            </div>
            <div>
              <Button onClick={saveEmail} disabled={busy === "email"} data-testid="em-connect-btn" className="rounded-full bg-emerald-700 hover:bg-emerald-800 text-white">
                <Sparkles className="h-4 w-4 mr-2" /> {busy === "email" ? "Verifying…" : "Connect provider"}
              </Button>
              <div className="text-[11px] text-slate-500 mt-2">Make sure your sending domain is verified inside your provider before going live.</div>
            </div>
          </div>
        ) : (
          <div className="space-y-4 text-sm">
            <div className="grid sm:grid-cols-2 gap-3">
              <div><span className="text-slate-500 text-xs">Provider</span><div>{em.provider}</div></div>
              <div><span className="text-slate-500 text-xs">API key</span><div className="font-mono-clinical">{em.api_key_masked}</div></div>
              <div><span className="text-slate-500 text-xs">From</span><div>{em.from_name ? `${em.from_name} <${em.from_email}>` : em.from_email}</div></div>
              <div><span className="text-slate-500 text-xs">Verified</span><div className="font-mono-clinical text-slate-800">{em.verified_at?.slice(0, 19).replace("T", " ")}Z</div></div>
            </div>
            <Button variant="outline" onClick={disconnectEmail} className="rounded-full border-rose-200 text-rose-700 hover:bg-rose-50 text-xs">
              <Trash2 className="h-3 w-3 mr-1.5" /> Disconnect
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
}
