import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/context/AuthProvider";
import { PawPrint } from "lucide-react";

export default function ProtectedRoute({ children, requireOnboarded = true }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="min-h-screen grid place-items-center bg-[#f8f9f6]">
        <div className="flex items-center gap-3 text-emerald-800">
          <div className="h-10 w-10 rounded-xl bg-emerald-700 grid place-items-center text-white animate-pulse">
            <PawPrint className="h-5 w-5" />
          </div>
          <div className="font-serif-display text-lg">Loading…</div>
        </div>
      </div>
    );
  }

  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />;

  if (requireOnboarded && user.clinic && user.clinic.onboarded === false && !location.pathname.startsWith("/onboarding")) {
    return <Navigate to="/onboarding" replace />;
  }

  return children;
}
