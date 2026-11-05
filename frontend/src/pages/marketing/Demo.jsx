import { useState } from "react";
import MarketingShell from "@/components/MarketingShell";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { CheckCircle2, Loader2 } from "lucide-react";
import { toast } from "sonner";

export default function Demo() {
  const [form, setForm] = useState({ name: "", email: "", clinic: "", message: "" });
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post("/marketing/demo", form);
      setDone(true);
      toast.success("Thanks — we'll be in touch within one business day.");
    } catch {
      toast.error("Something went wrong. Please email vetaura.app@gmail.com.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <MarketingShell>
      <section className="max-w-3xl mx-auto px-6 py-16">
        <div className="text-center">
          <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Book a demo</div>
          <h1 className="mt-2 font-serif-display text-4xl sm:text-5xl font-semibold text-emerald-950 tracking-tight">See Vetaura in your clinic.</h1>
          <p className="mt-3 text-slate-600">30 minutes. Live. On your cases. No slide deck.</p>
        </div>

        <Card className="mt-10 p-8 rounded-2xl border-emerald-100 bg-white shadow-sm">
          {done ? (
            <div className="text-center py-8">
              <CheckCircle2 className="h-12 w-12 text-emerald-600 mx-auto mb-3" />
              <div className="font-serif-display text-2xl font-semibold text-emerald-950">Thanks, {form.name.split(" ")[0]}.</div>
              <div className="text-slate-600 mt-2">We'll email you within one business day to schedule your demo.</div>
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-4">
              <div className="grid sm:grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="name">Your name</Label>
                  <Input id="name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="mt-1" data-testid="demo-name" />
                </div>
                <div>
                  <Label htmlFor="clinic">Clinic name</Label>
                  <Input id="clinic" required value={form.clinic} onChange={(e) => setForm({ ...form, clinic: e.target.value })} className="mt-1" data-testid="demo-clinic" />
                </div>
              </div>
              <div>
                <Label htmlFor="email">Work email</Label>
                <Input id="email" type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="mt-1" data-testid="demo-email" />
              </div>
              <div>
                <Label htmlFor="message">What would you like to see? (optional)</Label>
                <Textarea id="message" rows={4} value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} className="mt-1" data-testid="demo-message" />
              </div>
              <Button type="submit" disabled={busy} data-testid="demo-submit" className="w-full h-11 bg-emerald-700 hover:bg-emerald-800 text-white rounded-full">
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : "Request a demo"}
              </Button>
            </form>
          )}
        </Card>
      </section>
    </MarketingShell>
  );
}
