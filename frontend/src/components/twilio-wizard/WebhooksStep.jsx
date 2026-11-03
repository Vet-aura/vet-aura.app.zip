import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Copy, ArrowRight } from "lucide-react";
import { toast } from "sonner";

const copy = (t) => { navigator.clipboard.writeText(t); toast.success("Copied"); };

function UrlRow({ label, where, url, tid }) {
  return (
    <div className="rounded-xl border border-emerald-100 bg-emerald-50/40 p-3" data-testid={tid}>
      <div className="text-xs font-semibold text-emerald-900">{label}</div>
      <div className="text-[11px] text-slate-600 mb-1.5">{where}</div>
      <div className="flex items-center gap-2">
        <code className="flex-1 min-w-0 truncate font-mono-clinical text-xs text-slate-800 bg-white border border-slate-200 rounded-md px-2 py-1.5">{url}</code>
        <Button size="sm" variant="outline" onClick={() => copy(url)} data-testid={`${tid}-copy`} className="h-8 rounded-full text-xs"><Copy className="h-3 w-3 mr-1" /> Copy</Button>
      </div>
    </div>
  );
}

export function WebhooksStep({ webhooks }) {
  return (
    <div className="space-y-4" data-testid="tw-step-content-webhooks">
      <div>
        <h3 className="font-serif-display text-2xl font-semibold text-emerald-950">Point Twilio at Vetaura</h3>
        <p className="text-sm text-slate-600 mt-1">These private URLs let Vetaura answer texts, handle STOP/HELP and transcribe voicemail. They contain a secret token, so don't share them. Set the HTTP method to POST everywhere.</p>
      </div>
      {!webhooks ? (
        <div className="text-sm text-amber-800 bg-amber-50 border border-amber-100 rounded-xl p-3" data-testid="tw-webhooks-pending">Connect Twilio in step 6 first. Your URLs will show up here.</div>
      ) : (
        <div className="space-y-3">
          <UrlRow tid="tw-webhook-sms" label="Incoming messages" url={webhooks.sms_url}
            where="Twilio → Messaging → Services → your service → Integration → “Send a webhook” → Request URL." />
          <UrlRow tid="tw-webhook-voice" label="Incoming calls" url={webhooks.voice_url}
            where="Twilio → Phone Numbers → your number → Voice Configuration → “A call comes in” → Webhook." />
          <UrlRow tid="tw-webhook-status" label="Call status changes" url={webhooks.voice_status_callback}
            where="Same screen → “Call status changes”." />
          <div className="text-sm text-slate-700 rounded-xl border border-slate-200 p-3">
            <strong>Test it:</strong> text “HELP” to your clinic number from your mobile. You should get your clinic's help reply within a few seconds. Then text a normal question and it will show up in the AI Receptionist conversations.
          </div>
        </div>
      )}
      <div className="flex flex-wrap gap-2 pt-1">
        {[["/app/compliance", "Track A2P status"], ["/app/phone", "Phone & SMS"], ["/app/reminders", "Turn on care reminders"]].map(([to, label]) => (
          <Link key={to} to={to} className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-800 border border-emerald-200 rounded-full px-3 py-1.5 hover:bg-emerald-50 transition-colors">{label} <ArrowRight className="h-3 w-3" /></Link>
        ))}
      </div>
    </div>
  );
}
