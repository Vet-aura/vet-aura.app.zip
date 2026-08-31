import { useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api, setAuthToken } from "@/lib/api";
import { useAuth } from "@/context/AuthProvider";
import { PawPrint } from "lucide-react";
import { toast } from "sonner";

export default function AuthCallback() {
  const location = useLocation();
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const hasProcessed = useRef(false);

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const hash = location.hash || "";
    const m = hash.match(/session_id=([^&]+)/);
    if (!m) {
      navigate("/login", { replace: true });
      return;
    }
    const session_id = decodeURIComponent(m[1]);
    (async () => {
      try {
        const { data } = await api.post("/auth/session", { session_id });
        localStorage.setItem("vetaura_token", data.token);
        setAuthToken(data.token);
        setUser(data.user);
        // clear the hash
        window.history.replaceState({}, "", window.location.pathname);
        const isNew = data.user?.clinic?.onboarded === false;
        navigate(isNew ? "/onboarding" : "/app", { replace: true, state: { user: data.user } });
      } catch (e) {
        toast.error("Sign-in failed. Please try again.");
        navigate("/login", { replace: true });
      }
    })();
  }, [location.hash, navigate, setUser]);

  return (
    <div className="min-h-screen grid place-items-center bg-[#f8f9f6]">
      <div className="flex items-center gap-3 text-emerald-800">
        <div className="h-10 w-10 rounded-xl bg-emerald-700 grid place-items-center text-white animate-pulse">
          <PawPrint className="h-5 w-5" />
        </div>
        <div className="font-serif-display text-lg">Signing you in…</div>
      </div>
    </div>
  );
}
