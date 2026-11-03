import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Check, ChevronLeft, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { STEP_LABELS } from "./content";
import { GuideStep } from "./GuideStep";
import { ConnectStep } from "./ConnectStep";
import { WebhooksStep } from "./WebhooksStep";

function Stepper({ steps, current, done, onPick }) {
  return (
    <ol className="flex lg:flex-col gap-1 overflow-x-auto lg:overflow-visible pb-2 lg:pb-0 -mx-1 px-1" data-testid="tw-stepper">
      {steps.map((s, i) => (
        <li key={s}>
          <button type="button" onClick={() => onPick(s)} data-testid={`tw-step-${s}`} data-done={done.includes(s)}
            className={cn("w-full whitespace-nowrap flex items-center gap-2.5 rounded-xl px-3 py-2 text-left text-sm transition-colors",
              current === s ? "bg-emerald-900 text-white" : "text-slate-700 hover:bg-emerald-50")}>
            <span className={cn("h-6 w-6 rounded-full flex items-center justify-center text-xs font-semibold shrink-0",
              done.includes(s) ? "bg-emerald-500 text-white" : current === s ? "bg-white/15 text-white" : "bg-slate-100 text-slate-600")}>
              {done.includes(s) ? <Check className="h-3.5 w-3.5" /> : i + 1}
            </span>
            {STEP_LABELS[s]}
          </button>
        </li>
      ))}
    </ol>
  );
}

export function TwilioSetupWizard({ isOwner, onConnected }) {
  const [setup, setSetup] = useState(null);
  const [current, setCurrent] = useState("account");

  const load = useCallback(async (jump) => {
    try {
      const { data } = await api.get("/integrations/twilio/setup");
      setSetup(data);
      if (jump) setCurrent(data.steps.find((s) => !data.completed.includes(s)) || data.steps.at(-1));
    } catch { toast.error("Couldn't load the setup guide."); }
  }, []);
  useEffect(() => { load(true); }, [load]);

  if (!setup) return <div className="text-sm text-slate-400 py-6">Loading setup guide…</div>;
  const { steps } = setup;
  const done = [...new Set([...setup.completed, ...(setup.connected ? ["connect"] : [])])];
  const idx = steps.indexOf(current);

  async function markDone(next) {
    const completed = done.includes(current) ? done : [...done, current];
    if (isOwner) {
      try { await api.put("/integrations/twilio/setup", { completed }); } catch { toast.error("Couldn't save progress."); }
    }
    setSetup({ ...setup, completed });
    if (next && idx < steps.length - 1) setCurrent(steps[idx + 1]);
  }

  return (
    <div className="space-y-4" data-testid="tw-wizard">
      <div className="flex items-center gap-3">
        <Progress value={(done.length / steps.length) * 100} className="h-1.5 flex-1" />
        <span className="text-xs text-slate-500 shrink-0" data-testid="tw-progress-label">{done.length}/{steps.length} done</span>
      </div>
      <div className="grid lg:grid-cols-[220px_1fr] gap-6">
        <Stepper steps={steps} current={current} done={done} onPick={setCurrent} />
        <div className="min-w-0">
          {current === "connect" ? <ConnectStep connected={setup.connected} isOwner={isOwner} onConnected={async () => { await load(false); onConnected(); setCurrent("webhooks"); }} />
            : current === "webhooks" ? <WebhooksStep webhooks={setup.webhooks} />
            : <GuideStep stepKey={current} />}
          <div className="flex flex-wrap items-center justify-between gap-2 mt-6 pt-4 border-t border-emerald-100">
            <Button variant="ghost" disabled={idx === 0} onClick={() => setCurrent(steps[idx - 1])} data-testid="tw-prev" className="text-slate-600"><ChevronLeft className="h-4 w-4 mr-1" /> Back</Button>
            {current !== "connect" && (
              <Button onClick={() => markDone(true)} data-testid="tw-mark-done" className="rounded-full bg-emerald-700 hover:bg-emerald-800 text-white">
                {idx === steps.length - 1 ? "Finish setup" : "I've done this — next"} <ChevronRight className="h-4 w-4 ml-1" />
              </Button>
            )}
            {current === "connect" && setup.connected && <Button variant="outline" onClick={() => setCurrent("webhooks")} data-testid="tw-next" className="rounded-full">Next <ChevronRight className="h-4 w-4 ml-1" /></Button>}
          </div>
        </div>
      </div>
    </div>
  );
}
