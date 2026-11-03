import { ExternalLink, Copy, Clock, Lightbulb } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { STEP_CONTENT, SAMPLE_MESSAGES, OPT_IN_TEXT } from "./content";

const copy = (t) => { navigator.clipboard.writeText(t); toast.success("Copied"); };

function CopyBlock({ text, tid }) {
  return (
    <div className="flex items-start gap-2 rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-xs text-slate-700" data-testid={tid}>
      <span className="flex-1">{text}</span>
      <Button size="sm" variant="ghost" onClick={() => copy(text)} className="h-6 w-6 p-0 shrink-0"><Copy className="h-3 w-3" /></Button>
    </div>
  );
}

export function GuideStep({ stepKey }) {
  const c = STEP_CONTENT[stepKey];
  return (
    <div className="space-y-4" data-testid={`tw-step-content-${stepKey}`}>
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="font-serif-display text-2xl font-semibold text-emerald-950">{c.title}</h3>
          <span className="inline-flex items-center gap-1 text-[11px] text-slate-500"><Clock className="h-3 w-3" /> {c.time}</span>
        </div>
        <p className="text-sm text-slate-600 mt-1">{c.why}</p>
      </div>
      <ol className="space-y-2">
        {c.steps.map((s, i) => (
          <li key={s} className="flex gap-3 text-sm text-slate-800">
            <span className="h-6 w-6 rounded-full bg-emerald-100 text-emerald-800 text-xs font-semibold flex items-center justify-center shrink-0">{i + 1}</span>
            <span className="pt-0.5">{s}</span>
          </li>
        ))}
      </ol>
      {c.samples && (
        <div className="space-y-2">
          <div className="text-xs uppercase tracking-widest text-slate-500 font-semibold">Sample messages (paste into your campaign)</div>
          {SAMPLE_MESSAGES.map((m, i) => <CopyBlock key={m} text={m} tid={`tw-sample-${i}`} />)}
          <div className="text-xs uppercase tracking-widest text-slate-500 font-semibold pt-2">How clients opt in</div>
          <CopyBlock text={OPT_IN_TEXT} tid="tw-optin-text" />
        </div>
      )}
      {c.tip && <div className="flex gap-2 rounded-xl bg-amber-50 border border-amber-100 p-3 text-xs text-amber-900"><Lightbulb className="h-4 w-4 shrink-0" /> {c.tip}</div>}
      <div className="flex flex-wrap gap-2">
        {c.links.map(([label, href]) => (
          <a key={href} href={href} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-800 border border-emerald-200 rounded-full px-3 py-1.5 hover:bg-emerald-50 transition-colors">
            {label} <ExternalLink className="h-3 w-3" />
          </a>
        ))}
      </div>
    </div>
  );
}
