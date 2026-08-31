import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { UserPlus, Trash2, Copy, ShieldCheck, Mail } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthProvider";

const ROLE_LABEL = {
  owner: "Owner",
  vet: "Veterinarian",
  tech: "Technician",
  reception: "Reception",
};

export default function Team() {
  const { user } = useAuth();
  const [members, setMembers] = useState([]);
  const [invites, setInvites] = useState([]);
  const [form, setForm] = useState({ email: "", role: "vet", name: "" });
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      const [m, i] = await Promise.all([api.get("/team/members"), api.get("/team/invitations")]);
      setMembers(m.data); setInvites(i.data);
    } catch (e) { /* ignore */ }
  }
  useEffect(() => { load(); }, []);

  async function invite() {
    if (!form.email) return toast.info("Email required");
    setBusy(true);
    try {
      const { data } = await api.post("/team/invitations", form);
      if (data.delivered_by_email) {
        toast.success(`Invite emailed to ${form.email}`);
      } else {
        toast.info("Email not connected — copy the invite link below.");
      }
      setForm({ email: "", role: "vet", name: "" });
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Invite failed");
    } finally { setBusy(false); }
  }
  async function revoke(id) {
    if (!confirm("Revoke this invite?")) return;
    await api.delete(`/team/invitations/${id}`).catch(() => {});
    await load();
  }
  async function remove(user_id) {
    if (!confirm("Remove this team member?")) return;
    await api.delete(`/team/members/${user_id}`).catch(() => {});
    await load();
  }
  async function changeRole(user_id, role) {
    try {
      await api.patch(`/team/members/${user_id}/role`, { email: "placeholder@example.com", role });
      toast.success(`Role updated to ${role}`);
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed");
    }
  }

  const isOwner = user?.role === "owner" || !user?.role;

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-6 lg:py-10 space-y-6">
      <div>
        <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Team</div>
        <h1 className="font-serif-display text-3xl sm:text-4xl font-semibold text-emerald-950 tracking-tight mt-1">Invite your DVMs, techs and front desk.</h1>
        <p className="text-sm text-slate-600 mt-2 max-w-2xl">Roles gate what each teammate can see and do. Owners manage billing, integrations and the team. Others focus on the clinical work.</p>
      </div>

      {isOwner && (
        <Card className="p-5 rounded-2xl border-emerald-100 bg-white shadow-sm" data-testid="team-invite-card">
          <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold mb-3">Send an invite</div>
          <div className="grid sm:grid-cols-[1fr_140px_1fr_auto] gap-2 items-end">
            <label className="text-xs text-slate-600">Email
              <Input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value.trim() })} placeholder="dvm@your-clinic.com" data-testid="team-invite-email" />
            </label>
            <label className="text-xs text-slate-600">Role
              <Select value={form.role} onValueChange={(v) => setForm({ ...form, role: v })}>
                <SelectTrigger data-testid="team-invite-role"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="vet">Veterinarian</SelectItem>
                  <SelectItem value="tech">Technician</SelectItem>
                  <SelectItem value="reception">Reception</SelectItem>
                  <SelectItem value="owner">Owner</SelectItem>
                </SelectContent>
              </Select>
            </label>
            <label className="text-xs text-slate-600">Name (optional)
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Dr Jamie Chen" data-testid="team-invite-name" />
            </label>
            <Button onClick={invite} disabled={busy} data-testid="team-invite-btn" className="rounded-full bg-emerald-700 hover:bg-emerald-800 text-white h-9">
              <UserPlus className="h-3.5 w-3.5 mr-1.5" /> Send invite
            </Button>
          </div>
        </Card>
      )}

      <Card className="p-5 rounded-2xl border-emerald-100 bg-white shadow-sm" data-testid="team-members-card">
        <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold mb-3">Members ({members.length})</div>
        <div className="divide-y divide-slate-100">
          {members.map((m) => (
            <div key={m.user_id} className="py-3 grid grid-cols-[1fr_140px_120px] gap-3 items-center">
              <div>
                <div className="font-semibold text-slate-900">{m.name || m.email}</div>
                <div className="text-xs text-slate-500 font-mono-clinical">{m.email}</div>
              </div>
              {isOwner && m.user_id !== user?.user_id ? (
                <Select value={m.role || "vet"} onValueChange={(v) => changeRole(m.user_id, v)}>
                  <SelectTrigger className="h-8 text-xs" data-testid={`member-role-${m.email}`}><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="owner">Owner</SelectItem>
                    <SelectItem value="vet">Veterinarian</SelectItem>
                    <SelectItem value="tech">Technician</SelectItem>
                    <SelectItem value="reception">Reception</SelectItem>
                  </SelectContent>
                </Select>
              ) : (
                <Badge variant="outline" className="border-emerald-200 text-emerald-800 bg-emerald-50 text-[10px]">{ROLE_LABEL[m.role || "owner"] || m.role}</Badge>
              )}
              <div className="text-right">
                {isOwner && m.user_id !== user?.user_id && (
                  <Button size="sm" variant="outline" onClick={() => remove(m.user_id)} data-testid={`member-remove-${m.email}`} className="h-8 rounded-full border-rose-200 text-rose-700 hover:bg-rose-50 text-xs">
                    <Trash2 className="h-3 w-3 mr-1.5" /> Remove
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      </Card>

      {invites.length > 0 && (
        <Card className="p-5 rounded-2xl border-emerald-100 bg-white shadow-sm" data-testid="team-invites-card">
          <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold mb-3">Pending invites ({invites.filter((i) => i.status === "pending").length})</div>
          <div className="divide-y divide-slate-100">
            {invites.map((i) => (
              <div key={i.id} className="py-3 grid grid-cols-[1fr_140px_1fr_auto] gap-3 items-center">
                <div>
                  <div className="font-semibold text-slate-900">{i.email}</div>
                  <div className="text-xs text-slate-500">Invited by {i.invited_by}</div>
                </div>
                <Badge variant="outline" className={`text-[10px] ${i.status === "pending" ? "border-amber-200 text-amber-800 bg-amber-50" : "border-slate-200 text-slate-600 bg-slate-50"}`}>
                  {ROLE_LABEL[i.role]} · {i.status}
                </Badge>
                <div className="flex items-center gap-1 text-[11px] text-slate-500">
                  <span className="font-mono-clinical truncate max-w-[240px]">/invite/{i.token.slice(0, 10)}…</span>
                  <Button size="sm" variant="ghost" className="h-7 w-7 p-0" onClick={() => { navigator.clipboard.writeText(`${window.location.origin}/invite/${i.token}`); toast.success("Invite link copied"); }} data-testid={`invite-copy-${i.email}`}>
                    <Copy className="h-3 w-3" />
                  </Button>
                </div>
                <div>
                  {i.status === "pending" && (
                    <Button size="sm" variant="outline" onClick={() => revoke(i.id)} data-testid={`invite-revoke-${i.email}`} className="h-8 rounded-full border-rose-200 text-rose-700 hover:bg-rose-50 text-xs">Revoke</Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
