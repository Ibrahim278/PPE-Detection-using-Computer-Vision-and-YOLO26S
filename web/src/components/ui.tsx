import { AlertTriangle, CheckCircle2, HelpCircle, Loader2, ShieldAlert, UploadCloud, type LucideIcon } from "lucide-react";
import { useRef, useState, type ReactNode } from "react";

import type { Status, Summary } from "../lib/api";

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
      </div>
      {actions}
    </div>
  );
}

const STATUS_META: Record<Status | "unverified", { label: string; icon: LucideIcon; cls: string }> = {
  compliant: { label: "Helmet", icon: CheckCircle2, cls: "text-ok bg-ok/10 border-ok/30" },
  at_risk: { label: "At risk", icon: AlertTriangle, cls: "text-risk bg-risk/10 border-risk/30" },
  violation: { label: "No helmet", icon: ShieldAlert, cls: "text-bad bg-bad/10 border-bad/30" },
  unverified: { label: "Head not visible", icon: HelpCircle, cls: "text-unverified bg-unverified/10 border-unverified/30" },
};

export function StatusPill({ status, children }: { status: Status | "unverified"; children?: ReactNode }) {
  const m = STATUS_META[status];
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${m.cls}`}>
      <m.icon size={12} aria-hidden /> {children ?? m.label}
    </span>
  );
}

export function StatCard({ label, value, tone, hint }: { label: string; value: ReactNode; tone?: "ok" | "bad" | "risk"; hint?: string }) {
  const color = tone === "ok" ? "text-ok" : tone === "bad" ? "text-bad" : tone === "risk" ? "text-risk" : "text-ink";
  return (
    <div className="card px-4 py-3">
      <div className="text-xs font-medium uppercase tracking-wide text-muted">{label}</div>
      <div className={`tabular mt-1 text-2xl font-semibold ${color}`}>{value}</div>
      {hint && <div className="mt-0.5 text-xs text-muted">{hint}</div>}
    </div>
  );
}

/** "12 workers · 10 compliant · 2 violations" counter used on Live Monitor and image results. */
export function ComplianceCounter({ summary, compact }: { summary: Summary | null; compact?: boolean }) {
  const s = summary ?? { workers: 0, compliant: 0, at_risk: 0, violations: 0, unverified: 0 };
  const verified = s.workers - s.unverified;
  const rate = verified > 0 ? Math.round((s.compliant / verified) * 100) : null;
  return (
    <div className={`grid gap-3 ${compact ? "grid-cols-2 sm:grid-cols-4" : "grid-cols-2 lg:grid-cols-4"}`}>
      <StatCard label="Workers" value={s.workers} hint={s.unverified ? `${s.unverified} head not visible` : undefined} />
      <StatCard label="Compliant" value={s.compliant} tone="ok" />
      <StatCard label="Violations" value={s.violations} tone={s.violations ? "bad" : undefined}
        hint={s.at_risk ? `${s.at_risk} at risk` : undefined} />
      <StatCard label="Compliance" value={rate == null ? "–" : `${rate}%`}
        tone={rate == null ? undefined : rate === 100 ? "ok" : rate >= 80 ? "risk" : "bad"} hint="of workers with a visible head" />
    </div>
  );
}

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  const msg = error instanceof Error ? error.message : String(error);
  return (
    <div role="alert" className="flex items-start gap-2 rounded-lg border border-bad/40 bg-bad/10 px-3 py-2 text-sm text-bad">
      <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden /> <span>{msg}</span>
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-muted">
      <Loader2 size={16} className="animate-spin" aria-hidden /> {label}
    </span>
  );
}

export function ProgressBar({ value, tone = "brand" }: { value: number; tone?: "brand" | "ok" | "bad" }) {
  const bg = tone === "ok" ? "bg-ok" : tone === "bad" ? "bg-bad" : "bg-brand";
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-panel-2" role="progressbar"
      aria-valuenow={Math.round(value * 100)} aria-valuemin={0} aria-valuemax={100}>
      <div className={`h-full ${bg} transition-[width] duration-300`} style={{ width: `${Math.max(2, value * 100)}%` }} />
    </div>
  );
}

export function EmptyState({ icon: Icon, title, children }: { icon: LucideIcon; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
      <Icon size={28} className="text-muted" aria-hidden />
      <div className="font-medium">{title}</div>
      {children && <div className="max-w-sm text-sm text-muted">{children}</div>}
    </div>
  );
}

export function Dropzone({ accept, onFile, hint, disabled }: {
  accept: string; onFile: (f: File) => void; hint: string; disabled?: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  return (
    <button type="button" disabled={disabled}
      onClick={() => input.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); const f = e.dataTransfer.files[0]; if (f) onFile(f); }}
      className={`flex w-full flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-6 py-10 text-center transition
        ${over ? "border-brand bg-brand/5" : "border-line hover:border-muted"} disabled:opacity-50`}>
      <UploadCloud size={28} className="text-muted" aria-hidden />
      <span className="font-medium">Drop a file here or click to browse</span>
      <span className="text-sm text-muted">{hint}</span>
      <input ref={input} type="file" accept={accept} className="hidden"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = ""; }} />
    </button>
  );
}
