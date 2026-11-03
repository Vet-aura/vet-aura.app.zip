import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PhoneCall, Mail, RotateCcw, Trash2, ShieldCheck, Sparkles, BookOpen } from "lucide-react";
import { useAuth } from "@/context/AuthProvider";
import { TwilioSetupWizard } from "@/components/twilio-wizard/TwilioSetupWizard";
import { CheckResults } from "@/components/twilio-wizard/CheckResults";
import { toast } from "sonner";

export default function Integrations() {
  const [tw, setTw] = useState(null);
  const [em, setEm] = useState(null);
  const { user } = useAuth();
  const isOwner = (user?.role || "owner") === "owner";
  const [showGuide, setShowGuide] = useState(false);
  const [health, setHealth] = useState(null);
  const [emForm, setEmForm] = useState({ provider: "resend", api_key: "", from_email: "", from_name: "" });
  const [busy, setBusy] = useState(null);

  async function load() {
    try {
      const [t, e] = await Promise.all([api.get("/integrations/twilio"), api.get("/integrations/email")]);
      setTw(t.data); setEm(e.data);
    } catch (err) { console.warn("Integrations load failed:", err); }
  }
  useEffect(() => { load(); }, []);

  async function runHealth() {
    setBusy("health");
    try { setHealth((await api.post("/integrations/twilio/health")).data.checks); }
    catch (e) { toast.error(typeof e?.response?.data?.detail === "string" ? e.response.data.detail : "Health check failed."); }
    finally { setBusy(null); }
  }
  async function disconnectTwilio() {
    if (!confirm("Disconnect Twilio? Inbound calls and SMS will stop.")) return;
    try { await api.delete("/integrations/twilio"); toast.success("Twilio disconnected"); }
    catch { toast.error("Couldn't disconnect Twilio."); }
    setHealth(null);
    await load();
  }
  async function rotateWebhookToken() {
    setBusy("rotate");
    try {
      await api.post("/integrations/twilio/rotate-webhook-token");
      toast.success("Webhook URLs rotated. Paste the new URLs from the setup guide into Twilio.");
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

        {!tw?.connected || showGuide ? (
          <>
            {tw?.connected && <Button variant="ghost" size="sm" onClick={() => setShowGuide(false)} data-testid="tw-close-guide" className="mb-3 text-xs text-slate-600">← Back to connection summary</Button>}
            <TwilioSetupWizard isOwner={isOwner} onConnected={load} />
          </>
        ) : (
          <div className="space-y-4">
            <div className="grid sm:grid-cols-2 gap-3 text-sm">
              <div><span className="text-slate-500 text-xs">Account SID</span><div className="font-mono-clinical">{tw.account_sid_masked}</div></div>
              <div><span className="text-slate-500 text-xs">API Key SID</span><div className="font-mono-clinical">{tw.api_key_sid_masked}</div></div>
              <div><span className="text-slate-500 text-xs">Messaging Service SID</span><div className="font-mono-clinical">{tw.messaging_service_sid || <span className="text-amber-700">Not set. Add one so SMS goes through your approved campaign.</span>}</div></div>
              <div><span className="text-slate-500 text-xs">Last verified</span><div className="font-mono-clinical text-slate-800">{tw.verified_at?.slice(0, 19).replace("T", " ")}Z</div></div>
            </div>
            <CheckResults checks={health} />
            <div className="flex flex-wrap gap-2">
              {isOwner && <Button variant="outline" onClick={runHealth} disabled={busy === "health"} data-testid="tw-health-btn" className="rounded-full border-emerald-200 text-emerald-800 hover:bg-emerald-50 text-xs">
                <ShieldCheck className="h-3 w-3 mr-1.5" /> {busy === "health" ? "Checking…" : "Run health check"}
              </Button>}
              <Button variant="outline" onClick={() => setShowGuide(true)} data-testid="tw-open-guide" className="rounded-full border-emerald-200 text-emerald-800 hover:bg-emerald-50 text-xs">
                <BookOpen className="h-3 w-3 mr-1.5" /> Setup guide & webhook URLs
              </Button>
              {isOwner && <Button variant="outline" onClick={rotateWebhookToken} disabled={busy === "rotate"} data-testid="tw-rotate-btn" className="rounded-full border-emerald-200 text-emerald-800 hover:bg-emerald-50 text-xs">
                <RotateCcw className="h-3 w-3 mr-1.5" /> Rotate webhook token
              </Button>}
              {isOwner && <Button variant="outline" onClick={disconnectTwilio} data-testid="tw-disconnect-btn" className="rounded-full border-rose-200 text-rose-700 hover:bg-rose-50 text-xs">
                <Trash2 className="h-3 w-3 mr-1.5" /> Disconnect
              </Button>}
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
