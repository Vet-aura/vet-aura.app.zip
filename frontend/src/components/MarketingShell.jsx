import { useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { PawPrint, Menu } from "lucide-react";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";

const MARKETING_NAV = [
  { to: "/features", label: "Features", tid: "nav-features" },
  { to: "/pricing", label: "Pricing", tid: "nav-pricing" },
  { to: "/try-it", label: "Try it", tid: "nav-try-it" },
  { to: "/roi", label: "ROI", tid: "nav-roi" },
  { to: "/how-it-works", label: "For pet parents", tid: "nav-how" },
  { to: "/security", label: "Security", tid: "nav-security" },
  { to: "/faq", label: "FAQ", tid: "nav-faq" },
  { to: "/demo", label: "Book a demo", tid: "nav-demo" },
];

export default function MarketingShell({ children }) {
  const [menuOpen, setMenuOpen] = useState(false);
  return (
    <div className="min-h-screen bg-[#f8f9f6] text-slate-800 flex flex-col">
      <header className="border-b border-emerald-100 bg-white/70 backdrop-blur sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between gap-3">
          <Link to="/" className="flex items-center gap-2" data-testid="marketing-brand">
            <div className="h-10 w-10 rounded-xl bg-emerald-700 grid place-items-center text-white shadow-sm">
              <PawPrint className="h-5 w-5" />
            </div>
            <div className="flex flex-col">
              <span className="font-serif-display text-xl font-semibold text-emerald-900 leading-none">Vetaura</span>
              <span className="hidden sm:block text-[10px] uppercase tracking-widest text-emerald-700/70 mt-0.5">Clinical AI Copilot</span>
            </div>
          </Link>
          <nav className="hidden md:flex items-center gap-1">
            {MARKETING_NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                data-testid={n.tid}
                className={({ isActive }) => `px-3 py-2 text-sm font-medium rounded-lg transition-all ${isActive ? "text-emerald-900 bg-emerald-50" : "text-slate-600 hover:text-emerald-900 hover:bg-emerald-50/60"}`}
              >
                {n.label}
              </NavLink>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <Link to="/login" className="hidden sm:block text-sm font-semibold text-emerald-800 hover:text-emerald-900 px-3 py-2" data-testid="marketing-signin">Sign in</Link>
            <Link to="/signup" className="inline-flex items-center px-4 h-10 rounded-full bg-emerald-700 hover:bg-emerald-800 text-white text-sm font-semibold whitespace-nowrap" data-testid="marketing-start-trial">Start free trial</Link>
            <button type="button" onClick={() => setMenuOpen(true)} className="md:hidden h-10 w-10 grid place-items-center rounded-full border border-emerald-200 text-emerald-900" aria-label="Open menu" data-testid="marketing-menu-btn">
              <Menu className="h-5 w-5" />
            </button>
          </div>
        </div>
      </header>

      <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
        <SheetContent side="right" className="md:hidden w-72 bg-white" data-testid="marketing-menu">
          <SheetHeader><SheetTitle className="font-serif-display text-emerald-950">Vetaura</SheetTitle></SheetHeader>
          <nav className="mt-6 flex flex-col gap-1">
            {MARKETING_NAV.map((n) => (
              <NavLink key={n.to} to={n.to} onClick={() => setMenuOpen(false)} data-testid={`m-${n.tid}`}
                className={({ isActive }) => `px-3 py-3 rounded-lg text-base font-medium ${isActive ? "text-emerald-900 bg-emerald-50" : "text-slate-700"}`}>
                {n.label}
              </NavLink>
            ))}
            <Link to="/login" onClick={() => setMenuOpen(false)} className="mt-4 px-3 py-3 rounded-lg text-base font-semibold text-emerald-800 border border-emerald-200 text-center" data-testid="m-marketing-signin">Sign in</Link>
          </nav>
        </SheetContent>
      </Sheet>

      <main className="flex-1">{children}</main>

      <footer className="border-t border-emerald-100 bg-white/60">
        <div className="max-w-7xl mx-auto px-6 py-10 grid sm:grid-cols-5 gap-6 text-sm">
          <div>
            <div className="flex items-center gap-2 mb-3">
              <div className="h-8 w-8 rounded-lg bg-emerald-700 grid place-items-center text-white"><PawPrint className="h-4 w-4" /></div>
              <span className="font-serif-display text-lg font-semibold text-emerald-900">Vetaura</span>
            </div>
            <p className="text-slate-500 text-xs leading-relaxed">Vet-in-the-loop AI for busy veterinary practices.</p>
          </div>
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-widest text-slate-500 mb-3">Product</div>
            <ul className="space-y-1.5 text-slate-700">
              <li><Link to="/features" className="hover:text-emerald-800">Features</Link></li>
              <li><Link to="/pricing" className="hover:text-emerald-800">Pricing</Link></li>
              <li><Link to="/roi" className="hover:text-emerald-800">ROI</Link></li>
              <li><Link to="/how-it-works" className="hover:text-emerald-800">For pet parents</Link></li>
              <li><Link to="/security" className="hover:text-emerald-800">Security</Link></li>
              <li><Link to="/faq" className="hover:text-emerald-800">FAQ</Link></li>
            </ul>
          </div>
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-widest text-slate-500 mb-3">Legal</div>
            <ul className="space-y-1.5 text-slate-700">
              <li><Link to="/legal/terms" className="hover:text-emerald-800">Terms of Service</Link></li>
              <li><Link to="/legal/privacy" className="hover:text-emerald-800">Privacy Policy</Link></li>
              <li><a href="mailto:vetaura.app@gmail.com" className="hover:text-emerald-800">Request DPA / SCCs</a></li>
            </ul>
          </div>
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-widest text-slate-500 mb-3">Company</div>
            <ul className="space-y-1.5 text-slate-700">
              <li><Link to="/demo" className="hover:text-emerald-800">Book a demo</Link></li>
              <li><a href="mailto:vetaura.app@gmail.com" className="hover:text-emerald-800">Contact</a></li>
              <li><a href="mailto:vetaura.app@gmail.com" className="hover:text-emerald-800">Security</a></li>
            </ul>
          </div>
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-widest text-slate-500 mb-3">Powered by</div>
            <div className="text-slate-500 text-xs font-mono-clinical">Claude Opus 5.5<br />OpenAI Whisper</div>
          </div>
        </div>
        <div className="border-t border-emerald-100 py-4 text-center text-xs text-slate-400">
          © {new Date().getFullYear()} Vetaura · Drafts only — clinician review required.
        </div>
      </footer>
    </div>
  );
}
