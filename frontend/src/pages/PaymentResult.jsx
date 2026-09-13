import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthProvider";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";

export default function PaymentResult({ mode }) {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { refreshUser } = useAuth();
  const [status, setStatus] = useState(mode === "success" ? "polling" : "canceled");
  const session_id = params.get("session_id");

  useEffect(() => {
    if (mode !== "success" || !session_id) return;
    let tries = 0;
    let cancelled = false;
    const poll = async () => {
      while (!cancelled && tries < 25) {
        try {
          const { data } = await api.get(`/payments/status/${session_id}`);
          if (data.payment_status === "paid") {
            await refreshUser();
            setStatus("paid");
            return;
          }
        } catch (err) {
          // transient — payment webhook may not have landed yet; log and keep polling
          console.debug("payment status poll:", err?.response?.status || err?.message);
        }
        tries += 1;
        await new Promise((r) => setTimeout(r, 2000));
      }
      if (!cancelled) setStatus("timeout");
    };
    poll();
    return () => { cancelled = true; };
  }, [mode, session_id, refreshUser]);

  return (
    <div className="min-h-screen bg-[#f8f9f6] grid place-items-center p-6">
      <Card className="w-full max-w-md p-8 rounded-2xl border-emerald-100 bg-white shadow-lg text-center">
        {status === "polling" && (
          <>
            <Loader2 className="h-10 w-10 text-emerald-600 mx-auto mb-3 animate-spin" />
            <div className="font-serif-display text-2xl font-semibold text-emerald-950">Confirming your subscription…</div>
            <div className="text-sm text-slate-600 mt-2">Just a moment while Stripe finalizes.</div>
          </>
        )}
        {status === "paid" && (
          <>
            <CheckCircle2 className="h-10 w-10 text-emerald-600 mx-auto mb-3" />
            <div className="font-serif-display text-2xl font-semibold text-emerald-950">You're all set.</div>
            <div className="text-sm text-slate-600 mt-2">Your subscription is active. Back to the clinic.</div>
            <Button onClick={() => navigate("/app")} data-testid="payment-continue" className="mt-6 bg-emerald-700 hover:bg-emerald-800 text-white rounded-full w-full h-11">Open the clinic</Button>
          </>
        )}
        {status === "timeout" && (
          <>
            <div className="font-serif-display text-2xl font-semibold text-emerald-950">Still processing…</div>
            <div className="text-sm text-slate-600 mt-2">Your payment may take a moment. Check billing shortly.</div>
            <Button onClick={() => navigate("/app/billing")} data-testid="payment-check" className="mt-6 bg-emerald-700 hover:bg-emerald-800 text-white rounded-full w-full h-11">Go to billing</Button>
          </>
        )}
        {status === "canceled" && (
          <>
            <XCircle className="h-10 w-10 text-slate-400 mx-auto mb-3" />
            <div className="font-serif-display text-2xl font-semibold text-emerald-950">Checkout canceled.</div>
            <div className="text-sm text-slate-600 mt-2">No charge was made. You can try again any time.</div>
            <Button onClick={() => navigate("/app/billing")} data-testid="payment-back" className="mt-6 bg-emerald-700 hover:bg-emerald-800 text-white rounded-full w-full h-11">Back to billing</Button>
          </>
        )}
      </Card>
    </div>
  );
}
