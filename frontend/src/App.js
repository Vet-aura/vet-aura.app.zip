import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import AppShell from "@/components/AppShell";
import Landing from "@/pages/Landing";
import Dashboard from "@/pages/Dashboard";
import AmbientScribe from "@/pages/AmbientScribe";
import Patients from "@/pages/Patients";
import PatientDetail from "@/pages/PatientDetail";
import Inbox from "@/pages/Inbox";
import Schedule from "@/pages/Schedule";
import Differentials from "@/pages/Differentials";
import Discharge from "@/pages/Discharge";
import Handoff from "@/pages/Handoff";
import "@/App.css";

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/app" element={<AppShell />}>
            <Route index element={<Dashboard />} />
            <Route path="scribe" element={<AmbientScribe />} />
            <Route path="patients" element={<Patients />} />
            <Route path="patients/:id" element={<PatientDetail />} />
            <Route path="inbox" element={<Inbox />} />
            <Route path="schedule" element={<Schedule />} />
            <Route path="differentials" element={<Differentials />} />
            <Route path="discharge" element={<Discharge />} />
            <Route path="handoff" element={<Handoff />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster position="top-right" richColors />
    </div>
  );
}

export default App;
