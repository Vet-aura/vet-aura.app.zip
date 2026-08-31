import { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "@/context/AuthProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { PawPrint, Loader2 } from "lucide-react";
import { toast } from "sonner";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const from = location.state?.from || "/app";

  async function onSubmit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      const u = await login(email, password);
      toast.success(`Welcome back, ${u.name.split(" ")[0]}.`);
      navigate(u.clinic?.onboarded === false ? "/onboarding" : from, { replace: true });
    } catch {
      toast.error("Invalid email or password.");
    } finally {
      setBusy(false);
    }
  }

  function googleSignIn() {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + "/auth/callback";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  }

  return (
    <div className="min-h-screen bg-[#f8f9f6] grid lg:grid-cols-2">
      <div className="hidden lg:flex flex-col justify-between p-10 bg-emerald-900 text-emerald-50 relative overflow-hidden">
        <div className="flex items-center gap-2">
          <div className="h-10 w-10 rounded-xl bg-white/10 grid place-items-center"><PawPrint className="h-5 w-5" /></div>
          <div>
            <div className="font-serif-display text-2xl font-semibold">Vetaura</div>
            <div className="text-[10px] uppercase tracking-widest text-emerald-200/70">Clinical AI Copilot</div>
          </div>
        </div>
        <div>
          <h1 className="font-serif-display text-4xl leading-tight font-semibold text-white">
            "Vetaura gives me my day back with the animals — I no longer take notes home."
          </h1>
          <div className="mt-6 text-emerald-200/80 text-sm">Dr. Amaya Reyes · Meadow Ridge Veterinary</div>
        </div>
        <div className="text-xs text-emerald-200/60">© Vetaura · Vet-in-the-loop by design</div>
      </div>

      <div className="flex items-center justify-center p-6 sm:p-10">
        <Card className="w-full max-w-md p-8 rounded-2xl border-emerald-100 bg-white shadow-lg">
          <div className="lg:hidden flex items-center gap-2 mb-6">
            <div className="h-9 w-9 rounded-xl bg-emerald-700 grid place-items-center text-white"><PawPrint className="h-4 w-4" /></div>
            <span className="font-serif-display text-xl font-semibold text-emerald-950">Vetaura</span>
          </div>
          <h2 className="font-serif-display text-3xl font-semibold text-emerald-950">Welcome back</h2>
          <p className="text-sm text-slate-600 mt-1">Sign in to your clinic account.</p>

          <Button onClick={googleSignIn} data-testid="login-google-btn" variant="outline" className="w-full mt-6 h-11 border-slate-200 hover:bg-slate-50">
            <svg className="h-4 w-4 mr-2" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
            Continue with Google
          </Button>

          <div className="flex items-center gap-3 my-6">
            <div className="h-px bg-slate-200 flex-1" />
            <span className="text-xs text-slate-400 font-semibold uppercase tracking-widest">or</span>
            <div className="h-px bg-slate-200 flex-1" />
          </div>

          <form onSubmit={onSubmit} className="space-y-4">
            <div>
              <Label htmlFor="email">Work email</Label>
              <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required data-testid="login-email" className="mt-1" />
            </div>
            <div>
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required data-testid="login-password" className="mt-1" />
            </div>
            <Button type="submit" disabled={busy} data-testid="login-submit" className="w-full h-11 bg-emerald-700 hover:bg-emerald-800 text-white rounded-lg">
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : "Sign in"}
            </Button>
          </form>

          <p className="text-sm text-slate-600 text-center mt-6">
            New to Vetaura? <Link to="/signup" className="text-emerald-700 font-semibold hover:text-emerald-900" data-testid="login-to-signup">Start your 14-day trial</Link>
          </p>
        </Card>
      </div>
    </div>
  );
}
