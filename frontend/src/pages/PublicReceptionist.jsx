import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PawPrint, Send, AlertOctagon, CalendarPlus, Loader2, ArrowRight, CheckCircle2 } from "lucide-react";

function useSessionId(clinicId) {
  const key = `recept_session_${clinicId}`;
  const [id] = useState(() => {
    const existing = typeof window !== "undefined" ? sessionStorage.getItem(key) : null;
    if (existing) return existing;
    const fresh = `recept_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    if (typeof window !== "undefined") sessionStorage.setItem(key, fresh);
    return fresh;
  });
  return id;
}

export default function PublicReceptionist() {
  const { clinicId } = useParams();
  const sessionId = useSessionId(clinicId);
  const [config, setConfig] = useState(null);
  const [error, setError] = useState(null);
  const [msgs, setMsgs] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [booking, setBooking] = useState(null); // when AI signals booking_ready
  const [bookingSaved, setBookingSaved] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    api.get(`/receptionist/public/${clinicId}`)
      .then((r) => {
        setConfig(r.data);
        setMsgs([{ role: "assistant", text: r.data.greeting || "How can I help?" }]);
      })
      .catch(() => setError("This clinic's chat is not available right now."));
  }, [clinicId]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [msgs, busy]);

  async function send(text) {
    const t = (text ?? input).trim();
    if (!t) return;
    setMsgs((m) => [...m, { role: "user", text: t }]);
    setInput("");
    setBusy(true);
    try {
      const { data } = await api.post("/receptionist/chat", { clinic_id: clinicId, session_id: sessionId, message: t });
      setMsgs((m) => [...m, {
        role: "assistant", text: data.reply,
        emergency: data.emergency_detected,
        handoff: data.handoff,
      }]);
      if (data.booking_ready && data.collected) {
        setBooking({
          pet_name: data.collected.pet_name || "",
          species: data.collected.species || "Canine",
          breed: data.collected.breed || "",
          age: data.collected.age || "",
          reason: data.collected.reason || "",
          owner_name: data.collected.owner_name || "",
          owner_phone: data.collected.owner_phone || "",
          preferred_time: data.collected.preferred_time || "",
        });
      }
    } catch {
      setMsgs((m) => [...m, { role: "assistant", text: "Sorry — something went wrong. Please call the clinic directly.", handoff: "urgent" }]);
    } finally {
      setBusy(false);
    }
  }

  async function submitBooking() {
    if (!booking) return;
    setBusy(true);
    try {
      await api.post("/receptionist/book", {
        clinic_id: clinicId,
        session_id: sessionId,
        ...booking,
      });
      setBookingSaved(true);
      setMsgs((m) => [...m, { role: "assistant", text: `Thanks ${booking.owner_name.split(" ")[0]}! Your request is with our team. We'll call you at ${booking.owner_phone} to confirm.` }]);
      setBooking(null);
    } catch (e) {
      setMsgs((m) => [...m, { role: "assistant", text: e.response?.data?.detail || "Sorry, we couldn't submit the booking. A staff member will follow up." }]);
    } finally {
      setBusy(false);
    }
  }

  if (error) return <div className="min-h-screen grid place-items-center text-slate-500 text-sm p-6 text-center">{error}</div>;
  if (!config) return <div className="min-h-screen grid place-items-center"><Loader2 className="h-6 w-6 animate-spin text-emerald-700" /></div>;

  const primary = config.primary_color || "#236349";

  return (
    <div className="min-h-screen bg-[#f8f9f6]">
      <div className="max-w-lg mx-auto min-h-screen flex flex-col">
        <header className="text-white px-5 py-5 flex items-center gap-3 sticky top-0 z-20" style={{ background: primary }}>
          {config.logo_url ? (
            <img src={config.logo_url} alt="" className="h-11 w-11 rounded-xl bg-white/10 object-cover" />
          ) : (
            <div className="h-11 w-11 rounded-xl bg-white/15 grid place-items-center"><PawPrint className="h-5 w-5" /></div>
          )}
          <div className="flex-1 min-w-0">
            <div className="text-[10px] uppercase tracking-widest text-white/70 font-semibold">AI Front-desk Assistant</div>
            <div className="font-serif-display text-lg font-semibold truncate">{config.clinic_name}</div>
            <div className="text-[11px] text-white/80 truncate font-mono-clinical">{config.hours_text}</div>
          </div>
        </header>

        <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-3" data-testid="recept-transcript">
          {msgs.map((m, i) => (
            <div key={m.id || `${m.role}-${i}-${(m.text || "").slice(0, 24)}`} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${m.role === "user" ? "text-white" : "bg-white border border-emerald-100 text-slate-800"}`} style={m.role === "user" ? { background: primary } : {}}>
                {m.emergency && (
                  <div className="flex items-center gap-1 text-xs font-semibold text-rose-700 mb-1 uppercase tracking-widest"><AlertOctagon className="h-3 w-3" /> Possible emergency</div>
                )}
                {m.text}
                {m.handoff === "needed" && !m.emergency && (
                  <div className="text-[10px] text-slate-500 mt-1 uppercase tracking-widest font-semibold">A staff member will follow up</div>
                )}
              </div>
            </div>
          ))}
          {busy && (
            <div className="flex justify-start">
              <div className="rounded-2xl px-4 py-2.5 bg-white border border-emerald-100 text-slate-500 text-sm flex items-center gap-1">
                <span className="wave-bar h-1.5 w-1.5 rounded-full bg-emerald-500 inline-block" />
                <span className="wave-bar h-1.5 w-1.5 rounded-full bg-emerald-500 inline-block" style={{ animationDelay: "0.15s" }} />
                <span className="wave-bar h-1.5 w-1.5 rounded-full bg-emerald-500 inline-block" style={{ animationDelay: "0.3s" }} />
              </div>
            </div>
          )}
        </div>

        {booking && !bookingSaved && (
          <Card className="mx-4 mb-3 p-4 rounded-2xl border-emerald-200 bg-emerald-50/60" data-testid="recept-booking-card">
            <div className="text-xs uppercase tracking-widest text-emerald-800 font-semibold flex items-center gap-1"><CalendarPlus className="h-3 w-3" /> Confirm this booking</div>
            <div className="mt-3 grid grid-cols-2 gap-2">
              {[
                ["pet_name", "Pet name"], ["species", "Species"], ["breed", "Breed"], ["age", "Age"],
                ["owner_name", "Your name"], ["owner_phone", "Phone"], ["preferred_time", "Preferred time"],
              ].map(([k, label]) => (
                <div key={k} className={k === "reason" ? "col-span-2" : ""}>
                  <div className="text-[10px] uppercase tracking-widest text-slate-500 font-semibold mb-0.5">{label}</div>
                  <Input value={booking[k]} onChange={(e) => setBooking({ ...booking, [k]: e.target.value })} data-testid={`recept-book-${k}`} className="h-9 bg-white" />
                </div>
              ))}
              <div className="col-span-2">
                <div className="text-[10px] uppercase tracking-widest text-slate-500 font-semibold mb-0.5">Reason</div>
                <Input value={booking.reason} onChange={(e) => setBooking({ ...booking, reason: e.target.value })} data-testid="recept-book-reason" className="h-9 bg-white" />
              </div>
            </div>
            <Button
              onClick={submitBooking}
              disabled={busy}
              data-testid="recept-book-submit"
              style={{ background: primary }}
              className="w-full h-11 rounded-full mt-3 text-white hover:opacity-90"
            >
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <>Submit booking request <ArrowRight className="ml-2 h-4 w-4" /></>}
            </Button>
          </Card>
        )}

        {bookingSaved && (
          <Card className="mx-4 mb-3 p-4 rounded-2xl border-emerald-200 bg-emerald-50/60 flex items-center gap-2 text-sm text-emerald-900" data-testid="recept-booking-confirmed">
            <CheckCircle2 className="h-4 w-4" /> Booking request submitted. Our team will call to confirm.
          </Card>
        )}

        <div className="px-4 pb-4 pt-2 border-t border-emerald-100 bg-white/70 backdrop-blur">
          <div className="flex items-end gap-2">
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send()}
              placeholder="Type your question…"
              data-testid="recept-input"
              className="h-11 bg-white"
              disabled={busy}
            />
            <Button
              onClick={() => send()}
              disabled={busy || !input.trim()}
              data-testid="recept-send"
              style={{ background: primary }}
              className="h-11 w-11 rounded-full text-white hover:opacity-90 p-0 grid place-items-center flex-shrink-0"
            >
              <Send className="h-4 w-4" />
            </Button>
          </div>
          <div className="text-[10px] text-slate-400 mt-2 text-center">
            Emergency? Call <a className="text-slate-600 font-semibold" href={`tel:${(config.emergency_phone || "").replace(/\s+/g, "")}`}>{config.emergency_phone}</a>. AI drafts only — clinicians review before treatment.
          </div>
        </div>
      </div>
    </div>
  );
}
