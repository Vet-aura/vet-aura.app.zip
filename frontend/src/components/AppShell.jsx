import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { LayoutDashboard, Mic, PawPrint, Inbox, CalendarDays, ClipboardList, Stethoscope, MessagesSquare } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/app", icon: LayoutDashboard, label: "Dashboard", end: true, tid: "nav-dashboard" },
  { to: "/app/scribe", icon: Mic, label: "Ambient Scribe", tid: "nav-scribe" },
  { to: "/app/patients", icon: PawPrint, label: "Patients", tid: "nav-patients" },
  { to: "/app/schedule", icon: CalendarDays, label: "Schedule", tid: "nav-schedule" },
  { to: "/app/inbox", icon: Inbox, label: "Client Inbox", tid: "nav-inbox" },
  { to: "/app/differentials", icon: ClipboardList, label: "Differentials", tid: "nav-differentials" },
  { to: "/app/discharge", icon: MessagesSquare, label: "Discharge", tid: "nav-discharge" },
  { to: "/app/handoff", icon: Stethoscope, label: "Shift Handoff", tid: "nav-handoff" },
];

export default function AppShell() {
  const navigate = useNavigate();
  return (
    <div className="flex h-screen w-full bg-[#f8f9f6] text-slate-800 overflow-hidden">
      {/* Sidebar */}
      <aside className="hidden lg:flex w-60 flex-shrink-0 bg-white/95 backdrop-blur border-r border-emerald-100 flex-col p-4 z-30">
        <button
          data-testid="brand-home-btn"
          onClick={() => navigate("/")}
          className="flex items-center gap-2 px-2 py-2 mb-6 group"
        >
          <div className="h-9 w-9 rounded-xl bg-emerald-700 grid place-items-center text-white shadow-sm group-hover:shadow-md transition-all">
            <PawPrint className="h-5 w-5" />
          </div>
          <div className="flex flex-col items-start">
            <span className="font-serif-display text-lg font-semibold text-emerald-900 leading-none">Vetaura</span>
            <span className="text-[10px] uppercase tracking-widest text-emerald-700/70 mt-0.5">Clinical AI Copilot</span>
          </div>
        </button>

        <nav className="flex-1 flex flex-col gap-1">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              data-testid={n.tid}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all",
                  isActive
                    ? "bg-emerald-700 text-white shadow-sm"
                    : "text-slate-600 hover:bg-emerald-50 hover:text-emerald-900"
                )
              }
            >
              <n.icon className="h-4 w-4" />
              {n.label}
            </NavLink>
          ))}
        </nav>

        <div className="mt-4 rounded-xl border border-emerald-100 bg-emerald-50/60 p-3 text-xs text-emerald-900">
          <div className="font-semibold mb-1">Vet-in-the-loop</div>
          Every AI output is a draft. A clinician must review and sign before it affects care.
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="h-16 px-4 sm:px-6 bg-white/80 backdrop-blur border-b border-emerald-100 flex items-center justify-between z-20">
          <div className="lg:hidden flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-emerald-700 grid place-items-center text-white">
              <PawPrint className="h-4 w-4" />
            </div>
            <span className="font-serif-display text-lg font-semibold text-emerald-900">Vetaura</span>
          </div>
          <div className="hidden lg:block">
            <div className="text-xs uppercase tracking-widest text-slate-400 font-semibold">Meadow Ridge Veterinary</div>
            <div className="text-sm text-slate-600 font-mono-clinical">Today · {new Date().toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" })}</div>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2 text-xs">
              <span className="inline-flex h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-slate-600">Claude Sonnet 5 · Whisper</span>
            </div>
            <div className="h-9 w-9 rounded-full bg-gradient-to-br from-emerald-600 to-emerald-800 grid place-items-center text-white font-semibold text-sm shadow-sm" data-testid="user-avatar">
              DR
            </div>
          </div>
        </header>

        {/* Mobile bottom nav */}
        <nav className="lg:hidden fixed bottom-0 inset-x-0 z-40 bg-white/95 backdrop-blur border-t border-emerald-100 grid grid-cols-4 py-2 px-2">
          {NAV.slice(0, 4).map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              data-testid={`m-${n.tid}`}
              className={({ isActive }) =>
                cn(
                  "flex flex-col items-center justify-center gap-1 py-1 text-[10px] font-medium rounded-lg",
                  isActive ? "text-emerald-700" : "text-slate-500"
                )
              }
            >
              <n.icon className="h-5 w-5" />
              {n.label.split(" ")[0]}
            </NavLink>
          ))}
        </nav>

        <main className="flex-1 overflow-y-auto pb-20 lg:pb-0">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
