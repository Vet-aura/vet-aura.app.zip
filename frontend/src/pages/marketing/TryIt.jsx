import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import MarketingShell from "@/components/MarketingShell";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Globe, Sparkles, ArrowRight, PhoneCall, Clock, MapPin, PawPrint, MessageSquare } from "lucide-react";
import { toast } from "sonner";

export default function TryIt() {
  const [url, setUrl] = useState("");
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  async function spinUp() {
    if (!url.trim()) return toast.info("Paste your clinic website URL first.");
    let clean = url.trim();
    if (!/^https?:\/\//i.test(clean)) clean = "https://" + clean;
    setBusy(true);
    setResult(null);
    try {
      const { data } = await api.post("/marketing/try-it", { url: clean, email: email || null });
      setResult(data);
      toast.success("Your live receptionist demo is ready.");
    } catch (e) {
      const msg = e?.response?.data?.detail || "Could not read that URL. Try a different clinic page.";
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <MarketingShell>
      <section className="max-w-5xl mx-auto px-6 py-16">
        <div className="text-center max-w-2xl mx-auto">
          <Badge className="bg-amber-100 text-amber-800 border border-amber-200 uppercase tracking-widest text-[10px] font-semibold">New · no signup</Badge>
          <h1 className="mt-3 font-serif-display text-4xl sm:text-5xl font-semibold text-emerald-950 tracking-tight">Try the AI Receptionist on your real clinic.</h1>
          <p className="mt-4 text-slate-600">Paste your clinic's website. We'll spin up a live receptionist trained on your hours, services, and phone — in about 15 seconds. Ask it anything a pet parent would.</p>
        </div>

        <Card className="mt-10 p-6 sm:p-8 rounded-2xl border-emerald-100 bg-white shadow-sm">
          <div className="flex items-center gap-2 mb-3">
            <Globe className="h-4 w-4 text-emerald-700" />
            <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Your clinic website</div>
          </div>
          <div className="grid sm:grid-cols-[1fr_auto] gap-3">
            <Input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://your-clinic.com"
              data-testid="tryit-url-input"
              className="h-12"
            />
            <Button onClick={spinUp} disabled={busy} data-testid="tryit-submit-btn" className="h-12 rounded-full bg-emerald-700 hover:bg-emerald-800 text-white px-6">
              {busy ? "Reading your site…" : <span className="inline-flex items-center">Spin up receptionist <Sparkles className="ml-2 h-4 w-4" /></span>}
            </Button>
          </div>
          <div className="mt-3">
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Optional — email me a link so I can share this demo (24h)"
              data-testid="tryit-email-input"
            />
          </div>
          <p className="mt-3 text-[11px] text-slate-500">Nothing is saved to your live clinic. The demo expires in 24 hours.</p>
        </Card>

        {result && (
          <div className="mt-8 grid md:grid-cols-2 gap-6" data-testid="tryit-result">
            <Card className="p-6 rounded-2xl border-emerald-100 bg-emerald-50/40 shadow-sm">
              <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold mb-3">What we picked up</div>
              <div className="flex items-start gap-2 mb-3">
                <PawPrint className="h-4 w-4 text-emerald-700 mt-0.5" />
                <div>
                  <div className="font-semibold text-emerald-950">{result.profile.clinic_name}</div>
                  <div className="text-xs text-slate-500">{result.profile.source_url}</div>
                </div>
              </div>
              {result.profile.hours_text && (
                <div className="flex items-start gap-2 mb-2 text-sm text-slate-700">
                  <Clock className="h-4 w-4 text-emerald-700 mt-0.5" /> {result.profile.hours_text}
                </div>
              )}
              {result.profile.emergency_phone && (
                <div className="flex items-start gap-2 mb-2 text-sm text-slate-700">
                  <PhoneCall className="h-4 w-4 text-emerald-700 mt-0.5" /> {result.profile.emergency_phone}
                </div>
              )}
              {result.profile.address && (
                <div className="flex items-start gap-2 mb-2 text-sm text-slate-700">
                  <MapPin className="h-4 w-4 text-emerald-700 mt-0.5" /> {result.profile.address}
                </div>
              )}
              {result.profile.appt_types?.length > 0 && (
                <div className="mt-3">
                  <div className="text-[11px] uppercase tracking-widest text-slate-500 mb-1">Services detected</div>
                  <div className="flex flex-wrap gap-1.5">
                    {result.profile.appt_types.map((s, i) => (
                      <Badge key={i} variant="outline" className="border-emerald-200 text-emerald-800 bg-white text-[10px]">{s}</Badge>
                    ))}
                  </div>
                </div>
              )}
            </Card>

            <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm flex flex-col">
              <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold mb-3">Talk to your receptionist</div>
              <div className="rounded-xl border border-emerald-100 overflow-hidden flex-1">
                <iframe
                  title="Live receptionist"
                  src={result.receptionist_path}
                  className="w-full h-[420px] bg-white"
                  data-testid="tryit-iframe"
                />
              </div>
              <div className="mt-4 flex flex-col sm:flex-row gap-2">
                <Link to={result.receptionist_path} target="_blank" className="flex-1">
                  <Button variant="outline" className="w-full rounded-full border-emerald-300 text-emerald-800 hover:bg-emerald-50" data-testid="tryit-open-btn">
                    Open in full page <ArrowRight className="ml-2 h-3 w-3" />
                  </Button>
                </Link>
                <Link to="/signup" className="flex-1">
                  <Button className="w-full rounded-full bg-emerald-700 hover:bg-emerald-800 text-white" data-testid="tryit-signup-btn">
                    Claim this for real <Sparkles className="ml-2 h-3 w-3" />
                  </Button>
                </Link>
              </div>
            </Card>
          </div>
        )}

        {!result && (
          <div className="mt-10 grid sm:grid-cols-3 gap-4 text-sm">
            <Card className="p-5 rounded-2xl border-emerald-100 bg-white shadow-sm">
              <MessageSquare className="h-4 w-4 text-emerald-700 mb-2" />
              <div className="font-semibold text-emerald-950">Ask realistic questions</div>
              <div className="text-slate-600 text-xs mt-1">"Are you open Saturday?" · "Do you see rabbits?" · "How much is a dental?"</div>
            </Card>
            <Card className="p-5 rounded-2xl border-emerald-100 bg-white shadow-sm">
              <PawPrint className="h-4 w-4 text-emerald-700 mb-2" />
              <div className="font-semibold text-emerald-950">Try the emergency routing</div>
              <div className="text-slate-600 text-xs mt-1">Type "my dog collapsed" and watch the deterministic emergency handoff kick in.</div>
            </Card>
            <Card className="p-5 rounded-2xl border-emerald-100 bg-white shadow-sm">
              <PhoneCall className="h-4 w-4 text-emerald-700 mb-2" />
              <div className="font-semibold text-emerald-950">Book a fake appointment</div>
              <div className="text-slate-600 text-xs mt-1">Say "I want to book Bella for a vaccine Tuesday morning." Full booking flow — no real appointment created.</div>
            </Card>
          </div>
        )}
      </section>
    </MarketingShell>
  );
}
