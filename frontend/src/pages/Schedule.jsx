import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Calendar as CalendarComp } from "@/components/ui/calendar";
import { PawPrint } from "lucide-react";

export default function Schedule() {
  const [apts, setApts] = useState([]);
  const [date, setDate] = useState(new Date());

  useEffect(() => {
    api.get("/appointments").then((r) => setApts(r.data));
  }, []);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 lg:py-10 space-y-6">
      <div>
        <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">Schedule</div>
        <h1 className="font-serif-display text-3xl sm:text-4xl font-semibold text-emerald-950 tracking-tight mt-1">Today's appointments.</h1>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <Card className="p-4 rounded-2xl border-emerald-100 bg-white shadow-sm">
          <CalendarComp mode="single" selected={date} onSelect={(d) => d && setDate(d)} data-testid="schedule-calendar" />
        </Card>

        <Card className="lg:col-span-2 p-6 rounded-2xl border-emerald-100 bg-white shadow-sm">
          <div className="text-xs uppercase tracking-widest text-slate-500 font-semibold mb-4">
            {date.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })}
          </div>
          <div className="space-y-3">
            {apts.map((a) => (
              <div key={a.id} className="flex items-center gap-4 p-4 rounded-xl border border-emerald-50 hover:border-emerald-200 transition-all" data-testid={`sched-${a.id}`}>
                <div className="font-mono-clinical text-lg text-emerald-900 w-16">
                  {new Date(a.datetime).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                </div>
                <div className="h-10 w-10 rounded-xl bg-emerald-50 border border-emerald-100 grid place-items-center text-emerald-700">
                  <PawPrint className="h-5 w-5" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-slate-900 truncate">{a.patient?.name} <span className="text-slate-400 font-normal">· {a.patient?.breed}</span></div>
                  <div className="text-xs text-slate-500 truncate">{a.reason}</div>
                </div>
                <div className="text-right hidden sm:block">
                  <Badge variant="outline" className="border-emerald-200 text-emerald-800 bg-emerald-50">{a.type}</Badge>
                  <div className="text-xs text-slate-500 mt-1">{a.vet} · {a.room}</div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
