import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Smartphone } from "lucide-react";
import { toast } from "sonner";

const detail = (e, fb) => (typeof e?.response?.data?.detail === "string" ? e.response.data.detail : fb);

export function MyMobileCard() {
  const [state, setState] = useState({ phone: null, verified: false });
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => api.get("/me/mobile").then((r) => { setState(r.data); setPhone(r.data.phone || ""); }).catch(() => {}), []);
  useEffect(() => { load(); }, [load]);

  async function start() {
    setBusy(true);
    try { await api.post("/me/mobile/start", { phone }); setSent(true); toast.success("Code sent. Check your phone."); }
    catch (e) { toast.error(detail(e, "Couldn't send code.")); } finally { setBusy(false); }
  }
  async function verify() {
    setBusy(true);
    try { await api.post("/me/mobile/verify", { code }); setSent(false); setCode(""); toast.success("Mobile verified."); load(); }
    catch (e) { toast.error(detail(e, "Verification failed.")); } finally { setBusy(false); }
  }

  return (
    <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm" data-testid="my-mobile-card">
      <div className="flex items-center justify-between mb-2">
        <div className="text-xs uppercase tracking-widest text-slate-500 font-semibold flex items-center gap-2"><Smartphone className="h-3 w-3" /> My mobile number</div>
        {state.phone && <Badge variant="outline" className={state.verified ? "bg-emerald-50 text-emerald-800 border-emerald-200" : "bg-amber-50 text-amber-800 border-amber-200"} data-testid="my-mobile-status">{state.verified ? `Verified ${state.phone}` : "Not verified"}</Badge>}
      </div>
      <p className="text-sm text-slate-600 mb-3">Used to send you test copies of marketing blasts. We text a 6-digit code from your clinic's number.</p>
      <div className="flex flex-wrap gap-2">
        <Input className="max-w-xs" placeholder="(415) 555-0142" value={phone} onChange={(e) => setPhone(e.target.value)} data-testid="my-mobile-input" />
        <Button onClick={start} disabled={busy || phone.length < 7} variant="outline" data-testid="my-mobile-send-code" className="rounded-full border-emerald-300 text-emerald-800">{sent ? "Resend code" : "Send code"}</Button>
      </div>
      {sent && (
        <div className="flex flex-wrap gap-2 mt-3">
          <Input className="max-w-[160px] font-mono-clinical tracking-widest" inputMode="numeric" maxLength={6} placeholder="123456" value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} data-testid="my-mobile-code" />
          <Button onClick={verify} disabled={busy || code.length !== 6} data-testid="my-mobile-verify" className="rounded-full bg-emerald-700 hover:bg-emerald-800 text-white">Verify</Button>
        </div>
      )}
    </Card>
  );
}
