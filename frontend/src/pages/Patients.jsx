import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { PawPrint, AlertTriangle, Search } from "lucide-react";

export default function Patients() {
  const [pats, setPats] = useState([]);
  const [q, setQ] = useState("");

  useEffect(() => {
    api.get("/patients").then((r) => setPats(r.data)).catch(() => {});
  }, []);

  const filtered = pats.filter((p) => {
    const s = q.toLowerCase();
    return !s || p.name.toLowerCase().includes(s) || p.breed.toLowerCase().includes(s) || (p.owner?.name || "").toLowerCase().includes(s);
  });

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 lg:py-10 space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
        <div>
          <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Patients</div>
          <h1 className="font-serif-display text-3xl sm:text-4xl font-semibold text-emerald-950 tracking-tight mt-1">Every pet in your care.</h1>
        </div>
        <div className="relative w-full sm:w-72">
          <Search className="h-4 w-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search by pet, breed or owner"
            className="pl-9"
            data-testid="patients-search"
          />
        </div>
      </div>

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filtered.map((p) => (
          <Link
            key={p.id}
            to={`/app/patients/${p.id}`}
            data-testid={`patient-card-${p.id}`}
            className="group"
          >
            <Card className="p-5 rounded-2xl border-emerald-100 bg-white shadow-sm hover:border-emerald-300 hover:shadow-md transition-all h-full">
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div className="h-12 w-12 rounded-xl bg-emerald-50 border border-emerald-100 grid place-items-center text-emerald-700">
                    <PawPrint className="h-6 w-6" />
                  </div>
                  <div>
                    <div className="font-serif-display text-xl font-semibold text-emerald-950 leading-tight">{p.name}</div>
                    <div className="text-xs text-slate-500">{p.species} · {p.breed}</div>
                  </div>
                </div>
                {p.alerts?.length > 0 && (
                  <div className="flex items-center gap-1 text-amber-700 text-xs font-semibold">
                    <AlertTriangle className="h-3 w-3" /> {p.alerts.length}
                  </div>
                )}
              </div>
              <div className="grid grid-cols-3 gap-2 text-xs text-slate-600 font-mono-clinical mb-3">
                <div><div className="text-slate-400 uppercase tracking-widest text-[9px]">Age</div>{p.age_years}y</div>
                <div><div className="text-slate-400 uppercase tracking-widest text-[9px]">Weight</div>{p.weight_kg}kg</div>
                <div className="col-span-3"><div className="text-slate-400 uppercase tracking-widest text-[9px]">Sex</div>{p.sex}</div>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {(p.active_problems || []).slice(0, 3).map((prob, i) => (
                  <Badge key={i} variant="outline" className="text-[10px] border-emerald-200 text-emerald-800 bg-emerald-50">{prob}</Badge>
                ))}
              </div>
              <div className="mt-3 pt-3 border-t border-slate-100 text-xs text-slate-500">
                Owner: <span className="text-slate-800 font-medium">{p.owner?.name}</span>
              </div>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
