import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthProvider";
import { TemplateManager } from "@/components/marketing/TemplateManager";
import { BlastComposer } from "@/components/marketing/BlastComposer";
import { CampaignList } from "@/components/marketing/CampaignList";
import { toast } from "sonner";

export default function MarketingBlast() {
  const { user } = useAuth();
  const isOwner = (user?.role || "owner") === "owner";
  const [templates, setTemplates] = useState([]);
  const [campaigns, setCampaigns] = useState([]);
  const [ownerCount, setOwnerCount] = useState(1);

  const load = useCallback(async () => {
    try {
      const [t, c] = await Promise.all([api.get("/sms/marketing/templates"), api.get("/sms/marketing/campaigns")]);
      setTemplates(t.data); setCampaigns(c.data);
    } catch { toast.error("Couldn't load marketing data."); }
    try {
      const m = await api.get("/team/members");
      setOwnerCount(Math.max(1, (m.data || []).filter((u) => (u.role || "owner") === "owner").length));
    } catch { /* keep default of 1 */ }
  }, []);
  useEffect(() => { load(); }, [load]);

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6 lg:py-10 space-y-6" data-testid="marketing-page">
      <div>
        <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Marketing SMS</div>
        <h1 className="font-serif-display text-3xl sm:text-4xl font-semibold text-emerald-950 tracking-tight mt-1">Bulk texts, with guardrails.</h1>
        <p className="text-sm text-slate-600 mt-2 max-w-2xl">Locked wording, marketing-consent-only audiences, and an owner signs off before anything sends (a second owner, when your clinic has one). Approved blasts wait out your quiet hours automatically.</p>
      </div>
      <div className="grid lg:grid-cols-[1.1fr_1fr] gap-6 items-start">
        <div className="space-y-6">
          <BlastComposer templates={templates} onCreated={load} />
          <CampaignList campaigns={campaigns} me={user?.email} isOwner={isOwner} soloOwner={ownerCount <= 1} onChange={load} />
        </div>
        <TemplateManager templates={templates} isOwner={isOwner} onChange={load} />
      </div>
    </div>
  );
}
