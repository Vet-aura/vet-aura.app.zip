import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceArea, CartesianGrid } from "recharts";
import { CareItemsPanel } from "@/components/CareItemsPanel";
import { ArrowLeft, PawPrint, AlertTriangle, ClipboardList } from "lucide-react";

const RANGES = {
  creatinine: [0.8, 1.8],
  bun: [16, 36],
  sdma: [0, 14],
  phosphorus: [3.1, 5.5],
};

export default function PatientDetail() {
  const { id } = useParams();
  const [p, setP] = useState(null);

  useEffect(() => {
    api.get(`/patients/${id}`).then((r) => setP(r.data)).catch(() => {});
  }, [id]);

  if (!p) return <div className="p-10 text-slate-500">Loading…</div>;

  const weightData = (p.weights || []).map((w) => ({ x: new Date(w.date).toLocaleDateString(undefined, { month: "short", day: "numeric" }), Weight: w.weight_kg }));
  const labData = (p.labs || []).map((l) => ({
    x: new Date(l.date).toLocaleDateString(undefined, { month: "short", day: "numeric" }),
    Creatinine: l.creatinine, BUN: l.bun, SDMA: l.sdma, Phosphorus: l.phosphorus,
  }));

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 lg:py-10 space-y-6">
      <Link to="/app/patients" className="inline-flex items-center gap-1 text-xs text-emerald-700 font-semibold hover:text-emerald-900" data-testid="patient-back">
        <ArrowLeft className="h-3 w-3" /> Back to patients
      </Link>

      <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm">
        <div className="flex items-start gap-5">
          <div className="h-16 w-16 rounded-2xl bg-emerald-50 border border-emerald-100 grid place-items-center text-emerald-700">
            <PawPrint className="h-8 w-8" />
          </div>
          <div className="flex-1">
            <div className="flex items-center flex-wrap gap-2">
              <h1 className="font-serif-display text-3xl font-semibold text-emerald-950">{p.name}</h1>
              <Badge variant="outline" className="border-emerald-200 text-emerald-800 bg-emerald-50">{p.species}</Badge>
              <Badge variant="outline" className="border-slate-200 text-slate-700">{p.breed}</Badge>
            </div>
            <div className="text-sm text-slate-500 mt-1 font-mono-clinical">
              {p.age_years}y · {p.sex} · {p.weight_kg}kg · Chip {p.microchip}
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {(p.active_problems || []).map((pr, i) => (
                <Badge key={`${i}-${pr}`} variant="outline" className="border-emerald-200 text-emerald-800 bg-emerald-50">{pr}</Badge>
              ))}
            </div>
          </div>
          <div className="hidden md:block text-right">
            <div className="text-[10px] uppercase tracking-widest text-slate-400 font-semibold">Owner</div>
            <div className="font-semibold text-slate-900">{p.owner?.name}</div>
            <div className="text-xs text-slate-500">{p.owner?.email}</div>
            <div className="text-xs text-slate-500">{p.owner?.phone}</div>
          </div>
        </div>
        {(p.alerts || []).length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2">
            {p.alerts.map((a, i) => (
              <div key={`${i}-${a}`} className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-amber-50 border border-amber-200 text-amber-900 text-xs font-semibold">
                <AlertTriangle className="h-3 w-3" /> {a}
              </div>
            ))}
          </div>
        )}
      </Card>

      <Tabs defaultValue="visits">
        <TabsList data-testid="patient-tabs">
          <TabsTrigger value="visits" data-testid="tab-visits">Visits</TabsTrigger>
          <TabsTrigger value="trends" data-testid="tab-trends">Trends</TabsTrigger>
          <TabsTrigger value="labs" data-testid="tab-labs">Labs</TabsTrigger>
          <TabsTrigger value="notes" data-testid="tab-notes">Signed notes</TabsTrigger>
          <TabsTrigger value="care" data-testid="tab-care">Care due</TabsTrigger>
        </TabsList>

        <TabsContent value="visits" className="mt-4">
          <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm">
            <div className="divide-y divide-emerald-50">
              {(p.visits || []).map((v) => (
                <div key={v.id} className="py-3 flex flex-wrap items-center gap-3" data-testid={`visit-${v.id}`}>
                  <div className="font-mono-clinical text-xs text-slate-500 w-28">{new Date(v.date).toLocaleDateString()}</div>
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-slate-900">{v.reason}</div>
                    <div className="text-xs text-slate-500">{v.type} · {v.vet}</div>
                  </div>
                  {v.signed && <Badge variant="outline" className="border-emerald-200 text-emerald-800 bg-emerald-50">Signed</Badge>}
                </div>
              ))}
              {(p.visits || []).length === 0 && <div className="py-6 text-sm text-slate-500 text-center">No visits recorded yet.</div>}
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="trends" className="mt-4 grid lg:grid-cols-2 gap-4">
          <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm">
            <div className="text-xs uppercase tracking-widest text-slate-500 font-semibold mb-3">Weight (kg)</div>
            {weightData.length ? (
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={weightData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="x" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} domain={["dataMin - 0.5", "dataMax + 0.5"]} />
                  <Tooltip />
                  <Line type="monotone" dataKey="Weight" stroke="#236349" strokeWidth={2.5} dot={{ r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
            ) : <div className="text-sm text-slate-500">No weight history.</div>}
          </Card>

          <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm">
            <div className="text-xs uppercase tracking-widest text-slate-500 font-semibold mb-3">Renal panel trend</div>
            {labData.length ? (
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={labData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="x" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Line type="monotone" dataKey="Creatinine" stroke="#d97706" strokeWidth={2} />
                  <Line type="monotone" dataKey="SDMA" stroke="#236349" strokeWidth={2} />
                  <Line type="monotone" dataKey="Phosphorus" stroke="#7c3aed" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            ) : <div className="text-sm text-slate-500">No lab data.</div>}
          </Card>
        </TabsContent>

        <TabsContent value="labs" className="mt-4">
          <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[10px] uppercase tracking-widest text-slate-500 font-semibold border-b border-emerald-50">
                  <th className="py-2">Date</th>
                  {Object.keys(RANGES).map((k) => <th key={k} className="py-2">{k}</th>)}
                  <th className="py-2">USG</th>
                </tr>
              </thead>
              <tbody className="font-mono-clinical text-sm">
                {(p.labs || []).map((l) => (
                  <tr key={l.id} className="border-b border-emerald-50" data-testid={`lab-${l.id}`}>
                    <td className="py-2 text-slate-600">{new Date(l.date).toLocaleDateString()}</td>
                    {Object.keys(RANGES).map((k) => {
                      const [lo, hi] = RANGES[k];
                      const v = l[k];
                      const out = v != null && (v < lo || v > hi);
                      return <td key={k} className={`py-2 ${out ? "text-rose-700 font-semibold" : "text-slate-800"}`}>{v ?? "—"}</td>;
                    })}
                    <td className="py-2 text-slate-800">{l.usg ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {(p.labs || []).length === 0 && <div className="py-6 text-sm text-slate-500 text-center">No lab results yet.</div>}
          </Card>
        </TabsContent>

        <TabsContent value="notes" className="mt-4">
          <Card className="p-6 rounded-2xl border-emerald-100 bg-white shadow-sm space-y-4">
            {(p.soap_notes || []).map((n) => (
              <div key={n.id} className="p-4 rounded-xl border border-emerald-100" data-testid={`note-${n.id}`}>
                <div className="flex items-center justify-between mb-2">
                  <div className="text-xs text-slate-500 font-mono-clinical">{new Date(n.created_at).toLocaleString()}</div>
                  <Badge variant="outline" className="border-emerald-200 text-emerald-800 bg-emerald-50">{n.signed_by || "Draft"}</Badge>
                </div>
                <div className="grid sm:grid-cols-2 gap-3 text-sm">
                  <div><div className="text-[10px] uppercase tracking-widest text-sky-700 font-semibold">Subjective</div><div className="text-slate-700 whitespace-pre-wrap">{n.subjective}</div></div>
                  <div><div className="text-[10px] uppercase tracking-widest text-emerald-700 font-semibold">Objective</div><div className="text-slate-700 whitespace-pre-wrap">{n.objective}</div></div>
                  <div><div className="text-[10px] uppercase tracking-widest text-amber-700 font-semibold">Assessment</div><div className="text-slate-700 whitespace-pre-wrap">{n.assessment}</div></div>
                  <div><div className="text-[10px] uppercase tracking-widest text-purple-700 font-semibold">Plan</div><div className="text-slate-700 whitespace-pre-wrap">{n.plan}</div></div>
                </div>
              </div>
            ))}
            {(p.soap_notes || []).length === 0 && (
              <div className="text-center text-sm text-slate-500 py-6 flex flex-col items-center gap-2">
                <ClipboardList className="h-6 w-6 text-slate-300" />
                No signed notes yet. Draft one in the Ambient Scribe.
              </div>
            )}
          </Card>
        </TabsContent>

        <TabsContent value="care" className="mt-4">
          <CareItemsPanel patientId={p.id} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
