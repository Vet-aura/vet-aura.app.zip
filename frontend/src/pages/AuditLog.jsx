import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Activity, ShieldCheck } from "lucide-react";

const actionLabels = {
  ai_soap_draft: "SOAP drafted",
  soap_signed: "SOAP signed",
  ai_differentials: "Differentials generated",
  ai_discharge: "Discharge drafted",
  discharge_shared: "Discharge shared",
  ai_draft_reply: "Inbox draft generated",
  message_approved: "Message approved & sent",
  ai_handoff: "Shift handoff generated",
  whisper_transcribe: "Audio transcribed",
  clinic_updated: "Clinic settings updated",
  export_patients_csv: "Patients exported",
  export_notes_csv: "Notes exported",
};

const actionColor = {
  soap_signed: "border-emerald-200 text-emerald-800 bg-emerald-50",
  discharge_shared: "border-purple-200 text-purple-800 bg-purple-50",
  message_approved: "border-sky-200 text-sky-800 bg-sky-50",
  clinic_updated: "border-amber-200 text-amber-800 bg-amber-50",
};

export default function AuditLog() {
  const [items, setItems] = useState([]);

  useEffect(() => {
    api.get("/audit").then((r) => setItems(r.data)).catch(() => {});
  }, []);

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-6 lg:py-10 space-y-6">
      <div>
        <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Audit log</div>
        <h1 className="font-serif-display text-3xl sm:text-4xl font-semibold text-emerald-950 tracking-tight mt-1">Every AI draft, every signature.</h1>
        <p className="text-sm text-slate-600 mt-2 flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-emerald-700" /> Compliance-friendly log — user, timestamp and metadata for every action.</p>
      </div>

      <Card className="p-4 rounded-2xl border-emerald-100 bg-white shadow-sm">
        <div className="divide-y divide-emerald-50">
          {items.map((a) => (
            <div key={a.id} className="py-3 flex items-start gap-4" data-testid={`audit-${a.id}`}>
              <div className="mt-1 h-8 w-8 rounded-full bg-emerald-50 border border-emerald-100 grid place-items-center text-emerald-700 flex-shrink-0">
                <Activity className="h-4 w-4" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <Badge variant="outline" className={`text-[10px] ${actionColor[a.action] || "border-slate-200 text-slate-700 bg-slate-50"}`}>{actionLabels[a.action] || a.action}</Badge>
                  <div className="text-sm font-semibold text-slate-900">{a.user_name}</div>
                </div>
                {a.target && <div className="text-xs text-slate-500 font-mono-clinical mt-0.5 truncate">Target: {a.target}</div>}
                {a.metadata && Object.keys(a.metadata).length > 0 && (
                  <div className="text-xs text-slate-500 mt-0.5 truncate">
                    {Object.entries(a.metadata).map(([k, v]) => `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`).join(" · ")}
                  </div>
                )}
              </div>
              <div className="text-xs text-slate-400 font-mono-clinical flex-shrink-0">{new Date(a.at).toLocaleString()}</div>
            </div>
          ))}
          {items.length === 0 && <div className="py-10 text-center text-slate-500 text-sm">No activity yet — actions in the app will appear here.</div>}
        </div>
      </Card>
    </div>
  );
}
