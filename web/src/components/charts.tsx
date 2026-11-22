import { useMemo, useState, type ReactNode } from "react";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

import type { TimelinePoint, ViolationEvent } from "../lib/api";
import { clock, duration } from "../lib/format";

// Shared chart styling: recessive grid/axes, text in ink tokens, one series per chart (named by its title),
// so meaning never depends on telling colors apart.
export const tooltipStyle = {
  background: "var(--color-panel)", border: "1px solid var(--color-line)", borderRadius: 8,
  color: "var(--color-ink)", fontSize: 12,
};
/** Tooltip text stays in ink colors; the series color is only for the mark. */
export const tooltipItemStyle = { color: "var(--color-ink)" };
export const tooltipLabelStyle = { color: "var(--color-muted)", marginBottom: 2 };
const axis = { stroke: "var(--color-muted)", fontSize: 11, tickLine: false } as const;

export function ChartCard({ title, subtitle, right, children }: {
  title: string; subtitle?: string; right?: ReactNode; children: ReactNode;
}) {
  return (
    <section className="card p-4">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold">{title}</h2>
          {subtitle && <p className="mt-0.5 text-xs text-muted">{subtitle}</p>}
        </div>
        {right}
      </div>
      {children}
    </section>
  );
}

/* ---------------------------------------------------------------- compliance % over time */

/** Share of visible heads wearing a helmet in one frame (null when no head is visible). */
export const frameCompliance = (p: TimelinePoint) => {
  const visible = p.compliant + p.at_risk + p.violations;
  return visible ? (100 * p.compliant) / visible : null;
};

/** Worker-weighted average over frames; matches the API's summary.compliance_rate. */
export function averageCompliance(points: TimelinePoint[]) {
  let visible = 0;
  let ok = 0;
  for (const p of points) {
    visible += p.compliant + p.at_risk + p.violations;
    ok += p.compliant;
  }
  return visible ? ok / visible : null;
}

export function ComplianceChart({ points, offset, onSeek }: {
  points: TimelinePoint[]; offset: number; onSeek: (t: number) => void;
}) {
  const data = useMemo(() => points.map((p) => ({ t: p.t, pct: frameCompliance(p) })), [points]);
  return (
    <div className="h-48" role="img"
      aria-label={`Line chart of the percentage of visible workers wearing a helmet over time, ${data.length} points`}>
      <ResponsiveContainer>
        <LineChart data={data} margin={{ left: 0, right: 12, top: 8 }}
          onClick={(e) => { if (e?.activeLabel != null) onSeek(Number(e.activeLabel)); }}>
          <CartesianGrid stroke="var(--color-line)" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="t" type="number" domain={["dataMin", "dataMax"]} tickFormatter={(t) => clock(t + offset)} {...axis} />
          <YAxis domain={[0, 100]} ticks={[0, 50, 100]} tickFormatter={(v) => `${v}%`} width={46} {...axis} />
          <ReferenceLine y={100} stroke="var(--color-muted)" strokeDasharray="4 4"
            label={{ value: "target", position: "insideTopRight", fill: "var(--color-muted)", fontSize: 11 }} />
          <Tooltip contentStyle={tooltipStyle} itemStyle={tooltipItemStyle} labelStyle={tooltipLabelStyle} cursor={{ stroke: "var(--color-muted)" }}
            labelFormatter={(t) => clock(Number(t) + offset)}
            formatter={(v) => [typeof v === "number" ? `${v.toFixed(0)}%` : "no heads visible", "Wearing a helmet"]} />
          {/* gaps (no heads visible) stay gaps: no invented values */}
          <Line type="stepAfter" dataKey="pct" stroke="var(--color-chart)" strokeWidth={2} dot={false}
            activeDot={{ r: 4, stroke: "var(--color-panel)", strokeWidth: 2 }} connectNulls={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ---------------------------------------------------------------- per-worker violation timeline */

export function ViolationTimeline({ events, videoSeconds, offset, onSeek }: {
  events: ViolationEvent[]; videoSeconds: number; offset: number; onSeek: (t: number) => void;
}) {
  const rows = useMemo(() => {
    const byWorker = new Map<number, ViolationEvent[]>();
    for (const e of [...events].sort((a, b) => a.started_at_s - b.started_at_s)) {
      byWorker.set(e.worker_id, [...(byWorker.get(e.worker_id) ?? []), e]);
    }
    // One row per violation; workers with several violations get several rows labelled with the same id.
    return [...byWorker.entries()].flatMap(([w, evs]) => evs.map((e, i) => ({
      label: evs.length > 1 ? `#${w} (${i + 1})` : `#${w}`,
      range: [e.started_at_s, e.ended_at_s ?? videoSeconds] as [number, number],
      event: e,
    })));
  }, [events, videoSeconds]);

  return (
    <div style={{ height: 36 + rows.length * 30 }} role="img"
      aria-label={`Timeline of ${rows.length} violation${rows.length === 1 ? "" : "s"}: ` +
        rows.map((r) => `worker ${r.event.worker_id} from ${clock(r.range[0] + offset)} for ${duration(r.event.duration_s)}`).join("; ")}>
      <ResponsiveContainer>
        <BarChart data={rows} layout="vertical" margin={{ left: 0, right: 12, top: 4 }} barSize={14}>
          <CartesianGrid stroke="var(--color-line)" strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" domain={[0, Math.max(videoSeconds, 1)]} tickFormatter={(t) => clock(t + offset)} {...axis} />
          <YAxis type="category" dataKey="label" width={58} {...axis} />
          <Tooltip contentStyle={tooltipStyle} itemStyle={tooltipItemStyle} labelStyle={tooltipLabelStyle} cursor={{ fill: "var(--color-panel-2)" }}
            labelFormatter={(label) => `Worker ${label}`}
            formatter={(_v, _n, item) => {
              const e = (item.payload as { event: ViolationEvent }).event;
              const end = e.ended_at_s ?? videoSeconds;
              return [`${clock(e.started_at_s + offset)}–${clock(end + offset)} · ${duration(e.duration_s)}`, "No helmet"];
            }} />
          <Bar dataKey="range" fill="var(--color-bad)" radius={4} isAnimationActive={false} cursor="pointer"
            onClick={(d: { event?: ViolationEvent }) => d.event && onSeek(d.event.started_at_s)} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ---------------------------------------------------------------- live sparkline */

export interface TrendPoint { t: number; workers: number; violations: number }

export function Sparkline({ data, dataKey, label, color, now }: {
  data: TrendPoint[]; dataKey: "workers" | "violations"; label: string; color: string; now: number;
}) {
  const max = Math.max(1, ...data.map((d) => d[dataKey]));
  const current = data.length ? data[data.length - 1][dataKey] : 0;
  return (
    <div className="card px-4 py-3">
      <div className="flex items-baseline justify-between">
        <span className="text-xs font-medium uppercase tracking-wide text-muted">{label} · last 60 s</span>
        <span className="tabular text-sm font-semibold">{current}</span>
      </div>
      <div className="mt-1 h-14" role="img" aria-label={`${label} over the last 60 seconds, currently ${current}, peak ${max}`}>
        {data.length > 1 ? (
          <ResponsiveContainer>
            <AreaChart data={data} margin={{ top: 4, bottom: 0, left: 0, right: 0 }}>
              <XAxis dataKey="t" type="number" domain={[now - 60, now]} hide />
              <YAxis domain={[0, max]} allowDecimals={false} hide />
              <Tooltip contentStyle={tooltipStyle} itemStyle={tooltipItemStyle} labelStyle={tooltipLabelStyle} cursor={{ stroke: "var(--color-muted)" }}
                labelFormatter={(t) => `${Math.max(0, Math.round(now - Number(t)))} s ago`}
                formatter={(v: number) => [v, label]} />
              <Area type="stepAfter" dataKey={dataKey} stroke={color} strokeWidth={2} fill={color} fillOpacity={0.15}
                dot={false} isAnimationActive={false} />
            </AreaChart>
          </ResponsiveContainer>
        ) : <div className="grid h-full place-items-center text-xs text-muted">Waiting for data…</div>}
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- day x hour heatmap */

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const toLocal = (iso: string) => new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z");

/** Map a count to one of 5 sequential steps (0 = empty). */
function step(count: number, max: number) {
  if (!count) return 0;
  return Math.min(5, Math.max(1, Math.ceil((count / max) * 5)));
}

export function ViolationHeatmap({ events }: { events: ViolationEvent[] }) {
  const { grid, max, busiest } = useMemo(() => {
    const g = DAYS.map(() => Array<number>(24).fill(0));
    for (const e of events) {
      const d = toLocal(e.created_at);
      g[(d.getDay() + 6) % 7][d.getHours()] += 1; // Monday first
    }
    let m = 0;
    let top = { day: 0, hour: 0, n: 0 };
    g.forEach((row, di) => row.forEach((n, h) => { m = Math.max(m, n); if (n > top.n) top = { day: di, hour: h, n }; }));
    return { grid: g, max: m, busiest: top };
  }, [events]);
  const [hover, setHover] = useState<{ day: number; hour: number } | null>(null);
  const hourLabel = (h: number) => `${String(h).padStart(2, "0")}:00`;
  const hovered = hover ? grid[hover.day][hover.hour] : null;

  return (
    <div>
      <div className="mb-2 h-5 text-xs text-muted" aria-live="polite">
        {hover
          ? <><span className="text-ink">{DAYS[hover.day]} {hourLabel(hover.hour)}–{hourLabel((hover.hour + 1) % 24)}</span> · {hovered} violation{hovered === 1 ? "" : "s"}</>
          : busiest.n ? <>Busiest: <span className="text-ink">{DAYS[busiest.day]} {hourLabel(busiest.hour)}</span> ({busiest.n})</> : "No violations yet"}
      </div>
      <div className="overflow-x-auto pb-1">
        <div className="grid min-w-[560px] gap-[2px]" style={{ gridTemplateColumns: "36px repeat(24, minmax(0, 1fr))" }}
          role="img" aria-label={`Heatmap of violations by weekday and hour; busiest ${DAYS[busiest.day]} ${hourLabel(busiest.hour)} with ${busiest.n}`}
          onMouseLeave={() => setHover(null)}>
          <div />
          {Array.from({ length: 24 }, (_, h) => (
            <div key={h} className="text-center text-[10px] text-muted">{h % 3 === 0 ? h : ""}</div>
          ))}
          {grid.map((row, di) => (
            <Row key={di} day={DAYS[di]} row={row} max={max} onHover={(h) => setHover({ day: di, hour: h })} active={hover?.day === di ? hover.hour : null} />
          ))}
        </div>
      </div>
      <div className="mt-3 flex items-center justify-end gap-1.5 text-[11px] text-muted" aria-hidden>
        <span>Fewer</span>
        {[0, 1, 2, 3, 4, 5].map((s) => <span key={s} className="size-3 rounded-[3px]" style={{ background: cellColor(s) }} />)}
        <span>More</span>
      </div>
    </div>
  );
}

// Written out in full: Tailwind v4 only emits theme variables it can find literally in the source.
const HEAT = ["var(--color-panel-2)", "var(--color-heat-1)", "var(--color-heat-2)", "var(--color-heat-3)",
  "var(--color-heat-4)", "var(--color-heat-5)"];
const cellColor = (s: number) => HEAT[s];

function Row({ day, row, max, onHover, active }: {
  day: string; row: number[]; max: number; onHover: (h: number) => void; active: number | null;
}) {
  return (
    <>
      <div className="pr-1 text-right text-[11px] leading-5 text-muted">{day}</div>
      {row.map((n, h) => (
        <div key={h} onMouseEnter={() => onHover(h)} title={`${day} ${h}:00 · ${n}`}
          className={`h-5 rounded-[3px] ${active === h ? "outline-2 outline-ink" : ""}`}
          style={{ background: cellColor(step(n, max)) }} />
      ))}
    </>
  );
}
