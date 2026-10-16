import { NavLink, Outlet, useNavigate, Link } from "react-router-dom";
import { LayoutDashboard, Mic, PawPrint, Inbox, CalendarDays, ClipboardList, Stethoscope, MessagesSquare, CreditCard, Settings as SettingsIcon, Activity, LogOut, Sparkles, ListTodo, TrendingUp, PhoneCall, FileText, ShieldCheck, Users, Plug, Megaphone } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/context/AuthProvider";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";

const PRIMARY_NAV = [
  { to: "/app", icon: LayoutDashboard, label: "Dashboard", end: true, tid: "nav-dashboard" },
  { to: "/app/inbox", icon: Inbox, label: "Client Inbox", tid: "nav-inbox" },
  { to: "/app/tasks", icon: ListTodo, label: "Follow-ups", tid: "nav-tasks" },
  { to: "/app/care-gaps", icon: TrendingUp, label: "Care Gaps", tid: "nav-care-gaps" },
  { to: "/app/scribe", icon: Mic, label: "Ambient Scribe", tid: "nav-scribe" },
  { to: "/app/patients", icon: PawPrint, label: "Patients", tid: "nav-patients" },
  { to: "/app/schedule", icon: CalendarDays, label: "Schedule", tid: "nav-schedule" },
  { to: "/app/differentials", icon: ClipboardList, label: "Differentials", tid: "nav-differentials" },
  { to: "/app/discharge", icon: MessagesSquare, label: "Discharge", tid: "nav-discharge" },
  { to: "/app/handoff", icon: Stethoscope, label: "Shift Handoff", tid: "nav-handoff" },
];

const SECONDARY_NAV = [
  { to: "/app/receptionist", icon: PhoneCall, label: "AI Receptionist", tid: "nav-receptionist" },
  { to: "/app/phone", icon: PhoneCall, label: "Phone & SMS", tid: "nav-phone" },
  { to: "/app/compliance", icon: ShieldCheck, label: "SMS Compliance", tid: "nav-compliance" },
  { to: "/app/marketing", icon: Megaphone, label: "Marketing SMS", tid: "nav-marketing" },
  { to: "/app/scribe/templates", icon: FileText, label: "Scribe Templates", tid: "nav-templates" },
  { to: "/app/team", icon: Users, label: "Team", tid: "nav-team" },
  { to: "/app/integrations", icon: Plug, label: "Integrations", tid: "nav-integrations" },
  { to: "/app/billing", icon: CreditCard, label: "Billing", tid: "nav-billing" },
  { to: "/app/settings", icon: SettingsIcon, label: "Settings", tid: "nav-settings" },
  { to: "/app/audit", icon: Activity, label: "Audit Log", tid: "nav-audit" },
];

export default function AppShell() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const clinic = user?.clinic || {};

  const trialLeft = clinic.trial_ends_at
    ? Math.max(0, Math.ceil((new Date(clinic.trial_ends_at) - new Date()) / 86400000))
    : 0;

  const initials = (user?.name || "?").split(" ").map((s) => s[0]).slice(0, 2).join("").toUpperCase();

  async function onLogout() {
    await logout();
    navigate("/", { replace: true });
  }

  return (
    <div className="flex h-screen w-full bg-[#f8f9f6] text-slate-800 overflow-hidden">
      {/* Sidebar */}
      <aside className="hidden lg:flex w-60 flex-shrink-0 bg-white/95 backdrop-blur border-r border-emerald-100 flex-col p-4 z-30 overflow-y-auto">
        <button
          data-testid="brand-home-btn"
          onClick={() => navigate("/app")}
          className="flex items-center gap-2 px-2 py-2 mb-6 group"
        >
          <div className="h-9 w-9 rounded-xl bg-emerald-700 grid place-items-center text-white shadow-sm group-hover:shadow-md transition-all">
            <PawPrint className="h-5 w-5" />
          </div>
          <div className="flex flex-col items-start min-w-0">
            <span className="font-serif-display text-lg font-semibold text-emerald-900 leading-none">Vetaura</span>
            <span className="text-[10px] uppercase tracking-widest text-emerald-700/70 mt-0.5 truncate max-w-[8rem]">{clinic.name || "Clinic"}</span>
          </div>
        </button>

        <nav className="flex-1 flex flex-col gap-1">
          {PRIMARY_NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              data-testid={n.tid}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all",
                  isActive ? "bg-emerald-700 text-white shadow-sm" : "text-slate-600 hover:bg-emerald-50 hover:text-emerald-900"
                )
              }
            >
              <n.icon className="h-4 w-4" />
              {n.label}
            </NavLink>
          ))}

          <div className="mt-4 mb-1 px-3 text-[10px] uppercase tracking-widest text-slate-400 font-semibold">Clinic</div>
          {SECONDARY_NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              data-testid={n.tid}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all",
                  isActive ? "bg-emerald-700 text-white shadow-sm" : "text-slate-600 hover:bg-emerald-50 hover:text-emerald-900"
                )
              }
            >
              <n.icon className="h-4 w-4" />
              {n.label}
            </NavLink>
          ))}
        </nav>

        {clinic.plan_status === "trialing" && (
          <Link to="/app/billing" className="mt-4 block rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs hover:border-amber-300 transition-all" data-testid="trial-banner">
            <div className="flex items-center gap-1.5 font-semibold text-amber-900"><Sparkles className="h-3.5 w-3.5" /> {trialLeft} days left in trial</div>
            <div className="text-amber-800 mt-0.5">Upgrade any time — no interruption to your work.</div>
          </Link>
        )}
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="h-16 px-4 sm:px-6 bg-white/80 backdrop-blur border-b border-emerald-100 flex items-center justify-between z-20">
          <div className="lg:hidden flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-emerald-700 grid place-items-center text-white"><PawPrint className="h-4 w-4" /></div>
            <span className="font-serif-display text-lg font-semibold text-emerald-950">Vetaura</span>
          </div>
          <div className="hidden lg:block">
            <div className="text-xs uppercase tracking-widest text-slate-400 font-semibold truncate max-w-md">{clinic.name}</div>
            <div className="text-sm text-slate-600 font-mono-clinical">Today · {new Date().toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" })}</div>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2 text-xs">
              <span className="inline-flex h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-slate-600">Claude Sonnet 5 · Whisper</span>
            </div>
            <DropdownMenu>
              <DropdownMenuTrigger data-testid="user-menu" className="h-9 w-9 rounded-full bg-gradient-to-br from-emerald-600 to-emerald-800 grid place-items-center text-white font-semibold text-sm shadow-sm hover:shadow-md transition-all">
                {user?.picture ? <img src={user.picture} alt="" className="h-full w-full rounded-full object-cover" /> : initials}
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56 bg-white">
                <DropdownMenuLabel>
                  <div className="text-sm font-semibold text-slate-900">{user?.name}</div>
                  <div className="text-xs text-slate-500 truncate">{user?.email}</div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => navigate("/app/settings")} data-testid="menu-settings"><SettingsIcon className="h-4 w-4 mr-2" /> Clinic settings</DropdownMenuItem>
                <DropdownMenuItem onClick={() => navigate("/app/billing")} data-testid="menu-billing"><CreditCard className="h-4 w-4 mr-2" /> Billing</DropdownMenuItem>
                <DropdownMenuItem onClick={() => navigate("/app/audit")} data-testid="menu-audit"><Activity className="h-4 w-4 mr-2" /> Audit log</DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={onLogout} data-testid="menu-logout" className="text-rose-700 focus:text-rose-800 focus:bg-rose-50"><LogOut className="h-4 w-4 mr-2" /> Sign out</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>

        {/* Mobile bottom nav */}
        <nav className="lg:hidden fixed bottom-0 inset-x-0 z-40 bg-white/95 backdrop-blur border-t border-emerald-100 grid grid-cols-4 py-2 px-2">
          {PRIMARY_NAV.slice(0, 4).map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              data-testid={`m-${n.tid}`}
              className={({ isActive }) =>
                cn("flex flex-col items-center justify-center gap-1 py-1 text-[10px] font-medium rounded-lg", isActive ? "text-emerald-700" : "text-slate-500")
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
