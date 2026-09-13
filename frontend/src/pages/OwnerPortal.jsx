import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { PawPrint, Pill, AlertTriangle, CalendarPlus, Loader2 } from "lucide-react";
import { toast } from "sonner";

export default function OwnerPortal() {
  const { token } = useParams();
  const [doc, setDoc] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get(`/discharge/public/${token}`).then((r) => setDoc(r.data)).catch(() => setDoc(null)).finally(() => setLoading(false));
  }, [token]);

  if (loading) {
    return <div className="min-h-screen grid place-items-center"><Loader2 className="h-6 w-6 animate-spin text-emerald-700" /></div>;
  }
  if (!doc) {
    return <div className="min-h-screen grid place-items-center text-slate-500 text-sm">This discharge link is no longer available.</div>;
  }

  const primary = doc.primary_color || "#236349";
  const c = doc.content || {};

  return (
    <div className="min-h-screen bg-[#f8f9f6] text-slate-800">
      <div style={{ background: primary }} className="text-white">
        <div className="max-w-2xl mx-auto px-6 py-8 flex items-center gap-3">
          {doc.clinic_logo ? (
            <img src={doc.clinic_logo} alt="Clinic logo" className="h-12 w-12 rounded-xl bg-white/10 object-cover" />
          ) : (
            <div className="h-12 w-12 rounded-xl bg-white/15 grid place-items-center"><PawPrint className="h-6 w-6" /></div>
          )}
          <div>
            <div className="text-[10px] uppercase tracking-widest text-white/70 font-semibold">Discharge summary</div>
            <div className="font-serif-display text-2xl font-semibold">{doc.clinic_name}</div>
            <div className="text-xs text-white/80 mt-1">For {doc.pet_name} · Signed by {doc.signed_by}</div>
          </div>
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-6 py-8 space-y-6">
        {c.greeting && <div className="text-slate-800">{c.greeting}</div>}

        {c.summary && (
          <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm">
            <div className="text-[10px] uppercase tracking-widest font-semibold" style={{ color: primary }}>Today's visit</div>
            <div className="text-sm text-slate-700 leading-relaxed mt-2">{c.summary}</div>
          </Card>
        )}

        {(c.medications || []).length > 0 && (
          <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm">
            <div className="text-[10px] uppercase tracking-widest font-semibold flex items-center gap-1" style={{ color: primary }}><Pill className="h-3 w-3" /> Medications</div>
            <div className="mt-3 space-y-2">
              {c.medications.map((m, i) => (
                <div key={`${i}-${m.name}`} className="p-3 rounded-xl border" style={{ borderColor: primary + "33", background: primary + "0f" }}>
                  <div className="font-semibold" style={{ color: primary }}>{m.name}</div>
                  <div className="text-xs text-slate-600 font-mono-clinical">{m.dose} · {m.frequency}{m.duration ? ` · ${m.duration}` : ""}</div>
                  {m.notes && <div className="text-xs text-slate-600 mt-1">{m.notes}</div>}
                </div>
              ))}
            </div>
          </Card>
        )}

        {(c.home_care || []).length > 0 && (
          <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm">
            <div className="text-[10px] uppercase tracking-widest font-semibold" style={{ color: primary }}>Home care</div>
            <ul className="mt-2 text-sm text-slate-700 space-y-1 list-disc list-inside">
              {c.home_care.map((h, i) => <li key={`${i}-${h.slice(0,32)}`}>{h}</li>)}
            </ul>
          </Card>
        )}

        {(c.warning_signs || []).length > 0 && (
          <Card className="p-6 rounded-2xl border-amber-200 bg-amber-50">
            <div className="text-[10px] uppercase tracking-widest text-amber-900 font-semibold flex items-center gap-1"><AlertTriangle className="h-3 w-3" /> Call the clinic immediately if…</div>
            <ul className="mt-2 text-sm text-amber-900 space-y-1 list-disc list-inside">
              {c.warning_signs.map((w, i) => <li key={`${i}-${w.slice(0,32)}`}>{w}</li>)}
            </ul>
          </Card>
        )}

        {c.recheck && (
          <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm">
            <div className="text-[10px] uppercase tracking-widest font-semibold" style={{ color: primary }}>Recheck</div>
            <div className="text-sm text-slate-700 mt-2">{c.recheck}</div>
            <Button
              onClick={() => toast.info("Recheck request received. The clinic will call you within one business day.")}
              data-testid="owner-book-recheck"
              style={{ background: primary }}
              className="text-white rounded-full mt-4 h-11 px-6 hover:opacity-90"
            >
              <CalendarPlus className="h-4 w-4 mr-2" /> Request recheck appointment
            </Button>
          </Card>
        )}

        {c.closing && <div className="text-sm text-slate-600 italic">{c.closing}</div>}

        {doc.footer && (
          <div className="text-xs text-slate-500 pt-6 border-t border-slate-200 text-center">{doc.footer}</div>
        )}
        <div className="text-[10px] text-slate-400 text-center pb-6">Powered by Vetaura · Drafts are reviewed and signed by your clinician before delivery.</div>
      </div>
    </div>
  );
}
