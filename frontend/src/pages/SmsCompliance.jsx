import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ShieldCheck, ClipboardCheck, MessagesSquare, Ban, CircleCheck, AlertTriangle, Save, UserCheck } from "lucide-react";
import { toast } from "sonner";

const STATUS_LABELS = {
  ready: { label: "Ready to text", cls: "bg-emerald-100 text-emerald-800 border-emerald-200" },
  blocked: { label: "Blocked", cls: "bg-rose-100 text-rose-800 border-rose-200" },
  brand_pending: { label: "Brand pending", cls: "bg-amber-100 text-amber-800 border-amber-200" },
  campaign_pending: { label: "Campaign pending", cls: "bg-amber-100 text-amber-800 border-amber-200" },
  messaging_service_missing: { label: "Messaging service missing", cls: "bg-amber-100 text-amber-800 border-amber-200" },
  action_needed: { label: "Action needed", cls: "bg-amber-100 text-amber-800 border-amber-200" },
};

export default function SmsCompliance() {
  const [profile, setProfile] = useState(null);
  const [consent, setConsent] = useState([]);
  const [saving, setSaving] = useState(false);
  const [addConsent, setAddConsent] = useState({ phone_e164: "", consent_type: "care", source: "in_person_verbal", disclosure_version: "v1", contact_name: "" });

  async function load() {
    try {
      const [p, c] = await Promise.all([api.get("/compliance/sms/profile"), api.get("/compliance/sms/consent")]);
      setProfile(p.data); setConsent(c.data);
    } catch (e) { toast.error("Failed to load compliance data"); }
  }
  useEffect(() => { load(); }, []);

  async function save(partial) {
    setSaving(true);
    try {
      const { data } = await api.patch("/compliance/sms/profile", partial);
      setProfile(data);
      toast.success("Saved");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Save failed");
    } finally { setSaving(false); }
  }

  async function toggleCheck(key, val) {
    const checklist = { ...(profile?.checklist || {}), [key]: val };
    await save({ checklist });
  }

  async function optIn() {
    if (!addConsent.phone_e164 || !addConsent.disclosure_version) return toast.info("Phone and disclosure version required.");
    try {
      await api.post("/compliance/sms/consent", addConsent);
      toast.success("Consent recorded");
      setAddConsent({ ...addConsent, phone_e164: "", contact_name: "" });
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to record consent");
    }
  }

  async function optOut(phone, type) {
    if (!confirm(`Opt-out ${phone} from ${type}?`)) return;
    try {
      await api.post("/compliance/sms/consent/opt-out", { phone_e164: phone, consent_type: type, reason: "staff_manual" });
      toast.success("Opted out");
      await load();
    } catch (e) {
      toast.error("Failed");
    }
  }

  if (!profile) return <div className="p-10 text-slate-500">Loading…</div>;
  const readiness = profile.readiness || {};
  const badge = STATUS_LABELS[readiness.state] || { label: readiness.state, cls: "bg-slate-100 text-slate-700 border-slate-200" };

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6 lg:py-10 space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">SMS Compliance · A2P 10DLC</div>
          <h1 className="font-serif-display text-3xl sm:text-4xl font-semibold text-emerald-950 tracking-tight mt-1">Your Brand. Your Campaign. Your consent ledger.</h1>
          <p className="text-sm text-slate-600 mt-2 max-w-2xl">Vetaura is your orchestrator — <strong>your clinic</strong> owns the Twilio Brand, Campaign, and consent for every recipient. Complete each step in your Twilio Console, then attest below. No legal text is auto-generated for you.</p>
        </div>
        <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full border ${badge.cls} text-[11px] font-semibold`} data-testid="compliance-status">
          <ShieldCheck className="h-3.5 w-3.5" /> {badge.label} · {readiness.checklist_completed}/{readiness.checklist_total}
        </div>
      </div>

      {/* Checklist */}
      <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm" data-testid="compliance-checklist-card">
        <div className="flex items-center gap-2 mb-4">
          <ClipboardCheck className="h-4 w-4 text-emerald-700" />
          <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Compliance checklist</div>
        </div>
        <div className="grid md:grid-cols-2 gap-2">
          {(profile.checklist_definitions || []).map((item) => (
            <label key={item.key} className="flex items-start gap-3 p-3 rounded-xl border border-emerald-100 bg-emerald-50/20 hover:bg-emerald-50/40 cursor-pointer">
              <Checkbox
                checked={!!(profile.checklist || {})[item.key]}
                onCheckedChange={(v) => toggleCheck(item.key, !!v)}
                data-testid={`chk-${item.key}`}
                className="mt-0.5 border-emerald-300 data-[state=checked]:bg-emerald-700 data-[state=checked]:border-emerald-700"
              />
              <span className="text-sm text-slate-800 leading-snug">{item.label}</span>
            </label>
          ))}
        </div>
      </Card>

      {/* Brand + Campaign attestation */}
      <div className="grid md:grid-cols-2 gap-4">
        <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm" data-testid="compliance-brand-card">
          <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold mb-2">Brand attestation</div>
          <label className="text-xs text-slate-600">Twilio Brand SID
            <Input value={profile.brand_sid || ""} onChange={(e) => setProfile({ ...profile, brand_sid: e.target.value })} onBlur={() => save({ brand_sid: profile.brand_sid })} placeholder="BN…" data-testid="brand-sid" />
          </label>
          <label className="text-xs text-slate-600 mt-3 block">Status
            <Select value={profile.brand_status || "not_started"} onValueChange={(v) => save({ brand_status: v })}>
              <SelectTrigger data-testid="brand-status"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="not_started">Not started</SelectItem>
                <SelectItem value="pending">Pending review</SelectItem>
                <SelectItem value="approved">Approved</SelectItem>
                <SelectItem value="rejected">Rejected</SelectItem>
              </SelectContent>
            </Select>
          </label>
        </Card>
        <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm" data-testid="compliance-campaign-card">
          <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold mb-2">Campaign attestation</div>
          <label className="text-xs text-slate-600">Twilio Campaign SID
            <Input value={profile.campaign_sid || ""} onChange={(e) => setProfile({ ...profile, campaign_sid: e.target.value })} onBlur={() => save({ campaign_sid: profile.campaign_sid })} placeholder="CM…" data-testid="campaign-sid" />
          </label>
          <div className="grid grid-cols-2 gap-3 mt-3">
            <label className="text-xs text-slate-600">Use case
              <Select value={profile.campaign_use_case || "customer_care"} onValueChange={(v) => save({ campaign_use_case: v })}>
                <SelectTrigger data-testid="campaign-use-case"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="customer_care">Customer care</SelectItem>
                  <SelectItem value="account_notifications">Account notifications</SelectItem>
                  <SelectItem value="delivery_notifications">Delivery notifications</SelectItem>
                  <SelectItem value="marketing">Marketing (requires separate consent)</SelectItem>
                  <SelectItem value="mixed">Mixed</SelectItem>
                </SelectContent>
              </Select>
            </label>
            <label className="text-xs text-slate-600">Status
              <Select value={profile.campaign_status || "not_started"} onValueChange={(v) => save({ campaign_status: v })}>
                <SelectTrigger data-testid="campaign-status"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="not_started">Not started</SelectItem>
                  <SelectItem value="pending">Pending review</SelectItem>
                  <SelectItem value="approved">Approved</SelectItem>
                  <SelectItem value="rejected">Rejected</SelectItem>
                </SelectContent>
              </Select>
            </label>
          </div>
        </Card>
      </div>

      {/* Business identity */}
      <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm" data-testid="compliance-business-card">
        <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold mb-3">Business identity (matches your Twilio Brand)</div>
        <div className="grid sm:grid-cols-2 gap-3 text-xs text-slate-600">
          {[["legal_business_name", "Legal business name"], ["dba", "DBA / trade name"], ["ein", "EIN / tax ID"], ["entity_type", "Entity type"], ["business_address", "Business address"], ["business_website", "Business website"], ["business_email", "Business email"], ["business_phone", "Business phone"], ["authorized_contact_name", "Authorized contact name"], ["authorized_contact_email", "Authorized contact email"], ["opt_in_url", "Opt-in URL (screenshot on file)"], ["disclosure_language", "Exact opt-in disclosure text"]].map(([k, label]) => (
            <label key={k} className="block">{label}
              <Input value={profile[k] || ""} onChange={(e) => setProfile({ ...profile, [k]: e.target.value })} onBlur={() => save({ [k]: profile[k] })} data-testid={`biz-${k}`} />
            </label>
          ))}
        </div>
        <label className="block mt-3 text-xs text-slate-600">Texting purpose (for the clinic's records)
          <Textarea rows={2} value={profile.texting_purpose || ""} onChange={(e) => setProfile({ ...profile, texting_purpose: e.target.value })} onBlur={() => save({ texting_purpose: profile.texting_purpose })} data-testid="biz-purpose" />
        </label>
      </Card>

      {/* Consent ledger */}
      <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm" data-testid="compliance-consent-card">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <MessagesSquare className="h-4 w-4 text-emerald-700" />
            <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Consent ledger</div>
          </div>
          <div className="text-xs text-slate-500">{consent.length} records</div>
        </div>

        <div className="grid sm:grid-cols-[1fr_auto_auto_auto_auto] gap-2 items-end mb-4">
          <label className="text-xs text-slate-600">Phone (E.164)
            <Input value={addConsent.phone_e164} onChange={(e) => setAddConsent({ ...addConsent, phone_e164: e.target.value })} placeholder="+15551234567" data-testid="consent-phone" />
          </label>
          <label className="text-xs text-slate-600">Type
            <Select value={addConsent.consent_type} onValueChange={(v) => setAddConsent({ ...addConsent, consent_type: v })}>
              <SelectTrigger data-testid="consent-type" className="w-32"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="care">Care</SelectItem>
                <SelectItem value="marketing">Marketing</SelectItem>
              </SelectContent>
            </Select>
          </label>
          <label className="text-xs text-slate-600">Source
            <Input value={addConsent.source} onChange={(e) => setAddConsent({ ...addConsent, source: e.target.value })} className="w-40" data-testid="consent-source" />
          </label>
          <label className="text-xs text-slate-600">Disclosure version
            <Input value={addConsent.disclosure_version} onChange={(e) => setAddConsent({ ...addConsent, disclosure_version: e.target.value })} className="w-32" data-testid="consent-disclosure" />
          </label>
          <Button onClick={optIn} data-testid="consent-add-btn" className="rounded-full bg-emerald-700 hover:bg-emerald-800 text-white h-9"><UserCheck className="h-3.5 w-3.5 mr-1.5" /> Record opt-in</Button>
        </div>

        <div className="border-t border-emerald-100 -mx-6 px-6 pt-4">
          <div className="grid grid-cols-[1fr_100px_120px_140px_100px] gap-2 text-[11px] uppercase tracking-widest text-slate-500 font-semibold pb-2">
            <div>Phone</div><div>Type</div><div>Status</div><div>Source</div><div></div>
          </div>
          {consent.length === 0 && <div className="text-sm text-slate-500 py-6 text-center">No consent records yet. Record opt-ins as clients confirm at intake.</div>}
          {consent.slice(0, 100).map((r) => (
            <div key={r.phone_e164 + r.consent_type} className="grid grid-cols-[1fr_100px_120px_140px_100px] gap-2 items-center py-2 border-t border-slate-100 text-sm">
              <div className="font-mono-clinical">{r.phone_e164}</div>
              <div><Badge variant="outline" className={`text-[10px] ${r.consent_type === "marketing" ? "border-amber-200 text-amber-800 bg-amber-50" : "border-emerald-200 text-emerald-800 bg-emerald-50"}`}>{r.consent_type}</Badge></div>
              <div>
                {r.status === "opted_in"
                  ? <span className="inline-flex items-center gap-1 text-emerald-700"><CircleCheck className="h-3.5 w-3.5" /> Opted in</span>
                  : <span className="inline-flex items-center gap-1 text-rose-700"><Ban className="h-3.5 w-3.5" /> Opted out</span>}
              </div>
              <div className="text-xs text-slate-600">{r.last_source}</div>
              <div>
                {r.status === "opted_in" && (
                  <Button size="sm" variant="outline" onClick={() => optOut(r.phone_e164, r.consent_type)} className="h-7 text-xs rounded-full border-rose-200 text-rose-700 hover:bg-rose-50 px-2">Opt out</Button>
                )}
              </div>
            </div>
          ))}
        </div>
      </Card>

      <Card className="p-6 rounded-2xl border-amber-200 bg-amber-50/40 shadow-sm">
        <div className="flex gap-3">
          <AlertTriangle className="h-5 w-5 text-amber-700 mt-0.5" />
          <div>
            <div className="font-semibold text-amber-900">Vetaura does not draft your legal text.</div>
            <div className="text-sm text-amber-800 mt-1">Please have your attorney draft your website SMS Terms, Privacy Policy, and intake-form disclosure language. Store the exact wording in the "Disclosure language" field above so it's part of your consent audit trail.</div>
          </div>
        </div>
      </Card>
    </div>
  );
}
