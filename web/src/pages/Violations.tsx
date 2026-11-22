import { useQuery } from "@tanstack/react-query";
import { Download, ShieldCheck } from "lucide-react";
import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { EventList } from "../components/EventList";
import { EmptyState, ErrorBox, PageHeader, Spinner, StatCard } from "../components/ui";
import { api, type ViolationEvent } from "../lib/api";
import { duration } from "../lib/format";

type SourceFilter = "" | "job" | "stream";
type StatusFilter = "" | "open" | "closed";

export default function Violations() {
  const [source, setSource] = useState<SourceFilter>("");
  const [status, setStatus] = useState<StatusFilter>("");
  const summary = useQuery({ queryKey: ["events-summary"], queryFn: api.eventsSummary, refetchInterval: 5000 });
  const events = useQuery({
    queryKey: ["events", source, status],
    queryFn: () => api.events({ source, status, limit: 500 }),
    refetchInterval: 5000,
  });

  const buckets = useMemo(() => bucketize(events.data ?? []), [events.data]);
  const s = summary.data;

  return (
    <>
      <PageHeader title="Violations" subtitle="Every no-helmet incident from analysed videos and live monitoring."
        actions={<button className="btn-ghost" disabled={!events.data?.length} onClick={() => exportCsv(events.data ?? [])}>
          <Download size={16} aria-hidden /> Export CSV</button>} />

      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label="Total" value={s?.total ?? "–"} />
        <StatCard label="Active now" value={s?.open ?? "–"} tone={s?.open ? "bad" : undefined} />
        <StatCard label="Last 24 h" value={s?.last_24h ?? "–"} />
        <StatCard label="Avg duration" value={duration(s?.avg_duration_s)}
          hint={s ? `${s.by_source.job ?? 0} from videos · ${s.by_source.stream ?? 0} live` : undefined} />
      </div>

      <div className="mb-4 flex flex-wrap gap-3">
        <Select label="Source" value={source} onChange={(v) => setSource(v as SourceFilter)}
          options={[["", "All sources"], ["job", "Videos"], ["stream", "Live"]]} />
        <Select label="Status" value={status} onChange={(v) => setStatus(v as StatusFilter)}
          options={[["", "Any status"], ["open", "Active"], ["closed", "Resolved"]]} />
      </div>

      <ErrorBox error={events.error || summary.error} />
      {events.isLoading && <Spinner label="Loading…" />}

      {events.data && events.data.length === 0 && (
        <div className="card"><EmptyState icon={ShieldCheck} title="No violations recorded">
          Run a video in Analyze or start the Live Monitor; incidents appear here.</EmptyState></div>
      )}

      {events.data && events.data.length > 0 && (
        <div className="grid gap-6 xl:grid-cols-[1fr_400px]">
          <div className="card h-fit p-4">
            <h2 className="mb-1 text-sm font-semibold">Incidents over time</h2>
            <p className="mb-3 text-xs text-muted">Grouped by {buckets.unit}, based on when the incident was recorded.</p>
            <div className="h-64" role="img" aria-label={`Bar chart of violations per ${buckets.unit}`}>
              <ResponsiveContainer>
                <BarChart data={buckets.rows} margin={{ left: -20, right: 8, top: 4 }}>
                  <CartesianGrid stroke="var(--color-line)" strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="label" stroke="var(--color-muted)" fontSize={11} />
                  <YAxis allowDecimals={false} stroke="var(--color-muted)" fontSize={11} />
                  <Tooltip cursor={{ fill: "var(--color-panel-2)" }}
                    contentStyle={{ background: "var(--color-panel)", border: "1px solid var(--color-line)", borderRadius: 8 }} />
                  <Bar dataKey="video" name="Videos" stackId="a" fill="var(--color-brand)" isAnimationActive={false} />
                  <Bar dataKey="live" name="Live" stackId="a" fill="var(--color-bad)" radius={[3, 3, 0, 0]} isAnimationActive={false} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="card max-h-[75vh] overflow-y-auto">
            <h2 className="sticky top-0 border-b border-line bg-panel px-4 py-3 text-sm font-semibold">
              {events.data.length}{events.data.length === 500 ? "+" : ""} incident{events.data.length === 1 ? "" : "s"}
            </h2>
            <EventList events={events.data} showSource />
          </div>
        </div>
      )}
    </>
  );
}

function Select({ label, value, onChange, options }: {
  label: string; value: string; onChange: (v: string) => void; options: [string, string][];
}) {
  return (
    <label className="flex items-center gap-2 text-sm">
      <span className="text-muted">{label}</span>
      <select className="input w-auto py-1.5" value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    </label>
  );
}

const toDate = (iso: string) => new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z");

function bucketize(events: ViolationEvent[]) {
  if (!events.length) return { unit: "hour", rows: [] as { label: string; video: number; live: number }[] };
  const times = events.map((e) => toDate(e.created_at).getTime());
  const span = Math.max(...times) - Math.min(...times);
  const byDay = span > 2 * 86400_000;
  const map = new Map<string, { label: string; video: number; live: number; key: number }>();
  events.forEach((e, i) => {
    const d = new Date(times[i]);
    if (byDay) d.setHours(0, 0, 0, 0); else d.setMinutes(0, 0, 0);
    const key = d.getTime();
    const label = byDay ? d.toLocaleDateString(undefined, { month: "short", day: "numeric" })
      : d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
    const row = map.get(String(key)) ?? { label, video: 0, live: 0, key };
    if (e.source === "job") row.video += 1; else row.live += 1;
    map.set(String(key), row);
  });
  return { unit: byDay ? "day" : "hour", rows: [...map.values()].sort((a, b) => a.key - b.key) };
}

function exportCsv(events: ViolationEvent[]) {
  const cols = ["id", "created_at", "source", "source_id", "worker_id", "started_at_s", "duration_s", "status", "end_reason", "conf"] as const;
  const esc = (v: unknown) => { const s = v == null ? "" : String(v); return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
  const csv = [cols.join(","), ...events.map((e) => cols.map((c) => esc(e[c])).join(","))].join("\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  const a = Object.assign(document.createElement("a"), { href: url, download: `violations_${new Date().toISOString().slice(0, 10)}.csv` });
  a.click();
  URL.revokeObjectURL(url);
}
