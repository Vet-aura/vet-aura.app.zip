import { useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { KeyRound, ShieldCheck, Info } from "lucide-react";
import { toast } from "sonner";
import { CheckResults } from "./CheckResults";

const EMPTY = { account_sid: "", api_key_sid: "", api_key_secret: "", messaging_service_sid: "" };
const detail = (e, fb) => {
  const d = e?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => `${x.loc?.at(-1)}: ${(x.msg || "").replace(/^Value error, /, "")}`).join(" · ");
  return fb;
};

export function ConnectStep({ connected, isOwner, onConnected }) {
  const [f, setF] = useState(EMPTY);
  const [checks, setChecks] = useState(null);
  const [busy, setBusy] = useState(null);
  const credsOk = checks?.some((c) => c.key === "credentials" && c.status === "pass") && checks?.some((c) => c.key === "messaging_service" && c.status === "pass");
  const set = (k) => (e) => { setF({ ...f, [k]: e.target.value.trim() }); setChecks(null); };

  async function run(kind) {
    setBusy(kind);
    try {
      if (kind === "check") setChecks((await api.post("/integrations/twilio/check", f)).data.checks);
      else {
        const { data } = await api.post("/integrations/twilio", f);
        toast.success(`Connected to ${data.friendly_name || "Twilio"}`);
        setF(EMPTY); setChecks(null); onConnected();
      }
    } catch (e) { toast.error(detail(e, kind === "check" ? "Check failed." : "Could not connect.")); } finally { setBusy(null); }
  }

  if (!isOwner) return <div className="text-sm text-slate-600" data-testid="tw-connect-owner-only">Only a clinic owner can connect Twilio. Share this guide with them.</div>;
  return (
    <div className="space-y-4" data-testid="tw-step-content-connect">
      <div>
        <h3 className="font-serif-display text-2xl font-semibold text-emerald-950">Connect and test</h3>
        <p className="text-sm text-slate-600 mt-1">{connected ? "Twilio is already connected. Entering new values replaces the saved ones." : "Paste the four values from the earlier steps. \"Test connection\" only reads from Twilio. Nothing is sent and nothing is saved."}</p>
      </div>
      <div className="grid sm:grid-cols-2 gap-3">
        <label className="text-xs text-slate-600">Account SID (step 1)<Input value={f.account_sid} onChange={set("account_sid")} placeholder="AC…" data-testid="tw-account-sid" /></label>
        <label className="text-xs text-slate-600">Messaging Service SID (step 3)<Input value={f.messaging_service_sid} onChange={set("messaging_service_sid")} placeholder="MG…" data-testid="tw-msg-svc-sid" /></label>
        <label className="text-xs text-slate-600">API Key SID (step 5)<Input value={f.api_key_sid} onChange={set("api_key_sid")} placeholder="SK…" data-testid="tw-api-key-sid" /></label>
        <label className="text-xs text-slate-600">API Key Secret (step 5)<Input type="password" value={f.api_key_secret} onChange={(e) => { setF({ ...f, api_key_secret: e.target.value }); setChecks(null); }} placeholder="••••••••" data-testid="tw-api-key-secret" /></label>
      </div>
      <CheckResults checks={checks} />
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="outline" onClick={() => run("check")} disabled={!!busy} data-testid="tw-test-btn" className="rounded-full border-emerald-300 text-emerald-800">
          <ShieldCheck className="h-4 w-4 mr-2" /> {busy === "check" ? "Checking…" : "Test connection"}
        </Button>
        <Button onClick={() => run("save")} disabled={!!busy || !credsOk} data-testid="tw-connect-btn" className="rounded-full bg-emerald-700 hover:bg-emerald-800 text-white">
          <KeyRound className="h-4 w-4 mr-2" /> {busy === "save" ? "Connecting…" : "Save & connect"}
        </Button>
        <span className="text-[11px] text-slate-500 inline-flex items-center gap-1"><Info className="h-3 w-3" /> Test first. Save turns on once the key and Messaging Service pass. The secret is stored encrypted.</span>
      </div>
    </div>
  );
}
