import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthProvider";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Settings as SettingsIcon, Download } from "lucide-react";
import { toast } from "sonner";
import { SecurityAlertsCard } from "@/components/SecurityAlertsCard";
import { MyMobileCard } from "@/components/MyMobileCard";

export default function Settings() {
  const { user, refreshUser } = useAuth();
  const [form, setForm] = useState({ name: "", primary_color: "#236349", logo_url: "", discharge_footer: "" });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/clinic").then((r) => setForm({
      name: r.data.name || "",
      primary_color: r.data.primary_color || "#236349",
      logo_url: r.data.logo_url || "",
      discharge_footer: r.data.discharge_footer || "",
    }));
  }, []);

  async function save() {
    setBusy(true);
    try {
      await api.patch("/clinic", form);
      await refreshUser();
      toast.success("Clinic settings saved.");
    } catch {
      toast.error("Save failed.");
    } finally {
      setBusy(false);
    }
  }

  function downloadCsv(kind) {
    const token = localStorage.getItem("vetaura_token") || "";
    fetch(`${process.env.REACT_APP_BACKEND_URL}/api/export/${kind}.csv`, {
      headers: { Authorization: `Bearer ${token}` },
      credentials: "include",
    })
      .then((r) => r.blob())
      .then((b) => {
        const url = URL.createObjectURL(b);
        const a = document.createElement("a");
        a.href = url; a.download = `vetaura_${kind}.csv`;
        a.click(); URL.revokeObjectURL(url);
      })
      .catch(() => toast.error("Export failed."));
  }

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6 lg:py-10 space-y-6">
      <div>
        <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Settings</div>
        <h1 className="font-serif-display text-3xl sm:text-4xl font-semibold text-emerald-950 tracking-tight mt-1">Clinic settings.</h1>
      </div>

      <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm space-y-4">
        <div className="text-xs uppercase tracking-widest text-slate-500 font-semibold flex items-center gap-2"><SettingsIcon className="h-3 w-3" /> Branding</div>
        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <Label>Clinic name</Label>
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="settings-name" className="mt-1" />
          </div>
          <div>
            <Label>Primary color</Label>
            <div className="flex items-center gap-3 mt-1">
              <input type="color" value={form.primary_color} onChange={(e) => setForm({ ...form, primary_color: e.target.value })} className="h-10 w-14 rounded-lg border border-slate-200" data-testid="settings-color" />
              <Input value={form.primary_color} onChange={(e) => setForm({ ...form, primary_color: e.target.value })} className="font-mono-clinical" />
            </div>
          </div>
        </div>
        <div>
          <Label>Logo URL (optional)</Label>
          <Input value={form.logo_url} onChange={(e) => setForm({ ...form, logo_url: e.target.value })} placeholder="https://your-clinic.com/logo.png" data-testid="settings-logo" className="mt-1" />
          <div className="text-xs text-slate-500 mt-1">Displayed at the top of every owner discharge portal.</div>
        </div>
        <div>
          <Label>Discharge footer</Label>
          <Textarea rows={2} value={form.discharge_footer} onChange={(e) => setForm({ ...form, discharge_footer: e.target.value })} data-testid="settings-footer" className="mt-1" />
        </div>
        <div className="flex justify-end">
          <Button onClick={save} disabled={busy} data-testid="settings-save" className="bg-emerald-700 hover:bg-emerald-800 text-white rounded-full">
            Save changes
          </Button>
        </div>
      </Card>

      <MyMobileCard />

      {(user?.role || "owner") === "owner" && <SecurityAlertsCard />}

      <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm">
        <div className="text-xs uppercase tracking-widest text-slate-500 font-semibold mb-3">Data export</div>
        <div className="text-sm text-slate-600 mb-4">Download your patient list or signed notes as CSV any time.</div>
        <div className="flex flex-wrap gap-3">
          <Button onClick={() => downloadCsv("patients")} variant="outline" className="rounded-full border-emerald-300 text-emerald-800 hover:bg-emerald-50" data-testid="settings-export-patients"><Download className="h-4 w-4 mr-2" /> Patients CSV</Button>
          <Button onClick={() => downloadCsv("notes")} variant="outline" className="rounded-full border-emerald-300 text-emerald-800 hover:bg-emerald-50" data-testid="settings-export-notes"><Download className="h-4 w-4 mr-2" /> Signed notes CSV</Button>
        </div>
      </Card>
    </div>
  );
}
