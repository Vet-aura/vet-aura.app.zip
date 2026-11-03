import { CheckCircle2, AlertTriangle, XCircle } from "lucide-react";

const ICON = {
  pass: <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />,
  warn: <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0" />,
  fail: <XCircle className="h-4 w-4 text-rose-600 shrink-0" />,
};

export function CheckResults({ checks }) {
  if (!checks?.length) return null;
  return (
    <div className="rounded-xl border border-slate-200 divide-y divide-slate-100" data-testid="tw-check-results">
      {checks.map((c) => (
        <div key={c.key} className="flex items-start gap-2.5 p-3" data-testid={`tw-check-${c.key}`} data-status={c.status}>
          {ICON[c.status]}
          <div className="min-w-0">
            <div className="text-sm font-medium text-slate-900">{c.label}</div>
            {c.detail && <div className="text-xs text-slate-600 break-words">{c.detail}</div>}
          </div>
        </div>
      ))}
    </div>
  );
}
