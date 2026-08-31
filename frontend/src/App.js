import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider } from "@/context/AuthProvider";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Landing from "@/pages/Landing";
import Pricing from "@/pages/marketing/Pricing";
import Features from "@/pages/marketing/Features";
import FAQ from "@/pages/marketing/FAQ";
import Demo from "@/pages/marketing/Demo";
import Login from "@/pages/auth/Login";
import Signup from "@/pages/auth/Signup";
import AuthCallback from "@/pages/auth/AuthCallback";
import Onboarding from "@/pages/Onboarding";
import Dashboard from "@/pages/Dashboard";
import AmbientScribe from "@/pages/AmbientScribe";
import Patients from "@/pages/Patients";
import PatientDetail from "@/pages/PatientDetail";
import Inbox from "@/pages/Inbox";
import Schedule from "@/pages/Schedule";
import Differentials from "@/pages/Differentials";
import Discharge from "@/pages/Discharge";
import Handoff from "@/pages/Handoff";
import Billing from "@/pages/Billing";
import Settings from "@/pages/Settings";
import AuditLog from "@/pages/AuditLog";
import OwnerPortal from "@/pages/OwnerPortal";
import PaymentResult from "@/pages/PaymentResult";
import "@/App.css";

function AppRouter() {
  const location = useLocation();
  // OAuth callback detection: session_id lands in URL fragment.
  if (location.hash?.includes("session_id=")) return <AuthCallback />;

  return (
    <Routes>
      {/* Public marketing */}
      <Route path="/" element={<Landing />} />
      <Route path="/pricing" element={<Pricing />} />
      <Route path="/features" element={<Features />} />
      <Route path="/faq" element={<FAQ />} />
      <Route path="/demo" element={<Demo />} />

      {/* Auth */}
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/auth/callback" element={<AuthCallback />} />

      {/* Payment callbacks */}
      <Route path="/payment/success" element={<PaymentResult mode="success" />} />
      <Route path="/payment/cancel" element={<PaymentResult mode="cancel" />} />

      {/* Public owner portal */}
      <Route path="/d/:token" element={<OwnerPortal />} />

      {/* Onboarding (auth required, but no "onboarded" gate) */}
      <Route path="/onboarding" element={<ProtectedRoute requireOnboarded={false}><Onboarding /></ProtectedRoute>} />

      {/* App (auth + onboarded) */}
      <Route path="/app" element={<ProtectedRoute><AppShell /></ProtectedRoute>}>
        <Route index element={<Dashboard />} />
        <Route path="scribe" element={<AmbientScribe />} />
        <Route path="patients" element={<Patients />} />
        <Route path="patients/:id" element={<PatientDetail />} />
        <Route path="inbox" element={<Inbox />} />
        <Route path="schedule" element={<Schedule />} />
        <Route path="differentials" element={<Differentials />} />
        <Route path="discharge" element={<Discharge />} />
        <Route path="handoff" element={<Handoff />} />
        <Route path="billing" element={<Billing />} />
        <Route path="settings" element={<Settings />} />
        <Route path="audit" element={<AuditLog />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <AuthProvider>
          <AppRouter />
        </AuthProvider>
      </BrowserRouter>
      <Toaster position="top-right" richColors />
    </div>
  );
}

export default App;
