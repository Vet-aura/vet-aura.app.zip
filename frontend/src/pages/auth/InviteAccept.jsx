import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PawPrint, ShieldCheck, ArrowRight } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthProvider";

export default function InviteAccept() {
  const { token } = useParams();
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const [invite, setInvite] = useState(null);
  const [err, setErr] = useState(null);
  const [form, setForm] = useState({ name: "", password: "" });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get(`/invitations/${token}`)
      .then((r) => { setInvite(r.data); setForm((f) => ({ ...f, name: r.data.name || "" })); })
      .catch((e) => setErr(e?.response?.data?.detail || "Invite not found"));
  }, [token]);

  async function accept() {
    if (!form.name || form.password.length < 8) return toast.info("Enter your name and a password of at least 8 characters.");
    setBusy(true);
    try {
      const { data } = await api.post("/auth/signup", {
        email: invite.email,
        password: form.password,
        name: form.name,
        invite_token: token,
      });
      localStorage.setItem("token", data.token);
      setUser(data.user);
      toast.success(`Welcome to ${invite.clinic_name}!`);
      navigate("/app/inbox");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Signup failed");
    } finally { setBusy(false); }
  }

  if (err) {
    return (
      <div className="min-h-screen bg-emerald-50/30 flex items-center justify-center px-4">
        <Card className="p-8 rounded-3xl max-w-md text-center bg-white border-emerald-100 shadow-sm">
          <PawPrint className="h-6 w-6 text-emerald-700 mx-auto mb-3" />
          <div className="font-serif-display text-xl text-emerald-950">This invite can't be used</div>
          <div className="text-sm text-slate-600 mt-2">{err}</div>
          <Link to="/signup" className="inline-block mt-6"><Button className="rounded-full bg-emerald-700 hover:bg-emerald-800 text-white">Create your own account instead</Button></Link>
        </Card>
      </div>
    );
  }

  if (!invite) return <div className="min-h-screen bg-emerald-50/30 flex items-center justify-center text-slate-500">Loading…</div>;

  return (
    <div className="min-h-screen bg-emerald-50/40 flex items-center justify-center px-4 py-10">
      <Card className="w-full max-w-md p-8 rounded-3xl border-emerald-100 bg-white shadow-sm" data-testid="invite-accept-card">
        <PawPrint className="h-6 w-6 text-emerald-700 mb-3" />
        <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">You've been invited</div>
        <h1 className="font-serif-display text-2xl font-semibold text-emerald-950 mt-2">Join {invite.clinic_name} on Vetaura</h1>
        <p className="text-sm text-slate-600 mt-2">{invite.invited_by} invited you as a <strong>{invite.role}</strong>.</p>

        <div className="mt-6 space-y-3">
          <label className="text-xs text-slate-600 block">Email
            <Input value={invite.email} readOnly className="bg-slate-50" data-testid="invite-email" />
          </label>
          <label className="text-xs text-slate-600 block">Your name
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Dr Jamie Chen" data-testid="invite-name" />
          </label>
          <label className="text-xs text-slate-600 block">Choose a password
            <Input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder="At least 8 characters" data-testid="invite-password" />
          </label>
        </div>
        <Button onClick={accept} disabled={busy} data-testid="invite-accept-btn" className="w-full h-11 mt-6 rounded-full bg-emerald-700 hover:bg-emerald-800 text-white">
          {busy ? "Creating account…" : (<>Accept invitation <ArrowRight className="ml-2 h-4 w-4" /></>)}
        </Button>
        <div className="mt-4 text-[11px] text-slate-500 flex items-center gap-1"><ShieldCheck className="h-3 w-3" /> Your access is scoped to {invite.clinic_name}'s workspace only.</div>
      </Card>
    </div>
  );
}
