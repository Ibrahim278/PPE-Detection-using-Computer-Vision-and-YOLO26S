import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { ErrorBox, PageHeader, Spinner, StatCard } from "../components/ui";
import { api } from "../lib/api";
import { num, pct } from "../lib/format";

const METRICS = [["mAP50", "mAP@50"], ["mAP50-95", "mAP@50-95"], ["precision", "Precision"], ["recall", "Recall"]] as const;

export default function ModelPage() {
  const q = useQuery({ queryKey: ["model"], queryFn: api.model, staleTime: Infinity });
  if (q.isLoading) return <Spinner label="Loading…" />;
  if (q.error) return <ErrorBox error={q.error} />;
  const m = q.data!;
  const v3 = m.test_metrics;
  const v2 = m.baseline_v2;
  const compare = v3 && v2 ? METRICS.map(([k, label]) => ({ label, v2: v2[k], v3: v3[k] })) : [];

  return (
    <>
      <PageHeader title="Model" subtitle="YOLO26s fine-tuned on hard-hat images (helmet / head) plus a COCO person detector." />

      {v3 && (
        <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
          {METRICS.map(([k, label]) => (
            <StatCard key={k} label={label} value={num(v3[k])}
              hint={v2 ? `v2: ${num(v2[k])} (${v3[k] >= v2[k] ? "+" : ""}${((v3[k] - v2[k]) * 100).toFixed(1)} pts)` : undefined} />
          ))}
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-2">
        {compare.length > 0 && (
          <section className="card p-4">
            <h2 className="mb-1 text-sm font-semibold">v2 vs v3 on the same 502 test images</h2>
            <p className="mb-3 text-xs text-muted">Helmet + head only. Accuracy is effectively a tie; v3 adds tracking, events and a clean 2-class design.</p>
            <div className="h-64" role="img" aria-label="Grouped bar chart comparing v2 and v3 metrics">
              <ResponsiveContainer>
                <BarChart data={compare} margin={{ left: -16, right: 8, top: 4 }}>
                  <CartesianGrid stroke="var(--color-line)" strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="label" stroke="var(--color-muted)" fontSize={11} />
                  <YAxis domain={[0.5, 1]} stroke="var(--color-muted)" fontSize={11} />
                  <Tooltip formatter={(v: number) => v.toFixed(3)} cursor={{ fill: "var(--color-panel-2)" }}
                    contentStyle={{ background: "var(--color-panel)", border: "1px solid var(--color-line)", borderRadius: 8 }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="v2" name="v2 (notebook)" fill="var(--color-unverified)" radius={[3, 3, 0, 0]} isAnimationActive={false} />
                  <Bar dataKey="v3" name="v3 (current)" fill="var(--color-brand)" radius={[3, 3, 0, 0]} isAnimationActive={false} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>
        )}

        {v3 && (
          <section className="card overflow-x-auto p-4">
            <h2 className="mb-3 text-sm font-semibold">Per class (v3, test set)</h2>
            <table className="tabular w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-muted">
                <tr><th className="py-2 font-medium">Class</th><th className="font-medium">Precision</th><th className="font-medium">Recall</th>
                  <th className="font-medium">mAP@50</th><th className="font-medium">mAP@50-95</th><th className="font-medium">Threshold</th></tr>
              </thead>
              <tbody className="divide-y divide-line">
                {Object.entries(v3.per_class).map(([cls, c]) => (
                  <tr key={cls}>
                    <td className="py-2 font-medium capitalize">{cls === "head" ? "head (no helmet)" : cls}</td>
                    <td>{pct(c.precision)}</td><td>{pct(c.recall)}</td><td>{num(c.mAP50)}</td><td>{num(c["mAP50-95"])}</td>
                    <td>{num(m.thresholds[cls], 2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-3 text-xs text-muted">Thresholds are tuned per class to the confidence with the best F1 on the test set.</p>
          </section>
        )}

        <section className="card p-4">
          <h2 className="mb-3 text-sm font-semibold">How alerts work</h2>
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
            <dt className="text-muted">Alert after</dt><dd>{m.smoothing.min_violation_s} s of a bare head on the same tracked worker</dd>
            <dt className="text-muted">Resolve after</dt><dd>{m.smoothing.resolve_s} s with a helmet, or {m.smoothing.lost_s} s out of view</dd>
            <dt className="text-muted">Smoothing</dt><dd>moving average of “bare head” per worker (α = {m.smoothing.ema_alpha})</dd>
            <dt className="text-muted">People</dt><dd>{m.person_model ? `COCO detector (${m.person_model}); people whose head isn’t visible count as “head not visible”` : "disabled"}</dd>
            <dt className="text-muted">Running on</dt><dd className="uppercase">{m.device} · {m.imgsz}px</dd>
          </dl>
        </section>

        {m.benchmark && m.benchmark.length > 0 && (
          <section className="card overflow-x-auto p-4">
            <h2 className="mb-3 text-sm font-semibold">Speed (Apple M5, detector only)</h2>
            <table className="tabular w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-muted">
                <tr><th className="py-2 font-medium">Device</th><th className="font-medium">Median</th><th className="font-medium">p95</th><th className="font-medium">FPS</th></tr>
              </thead>
              <tbody className="divide-y divide-line">
                {m.benchmark.map((b) => (
                  <tr key={b.device + b.weights}><td className="py-2 uppercase">{b.device}</td><td>{b.median_ms} ms</td><td>{b.p95_ms} ms</td><td>{b.fps}</td></tr>
                ))}
              </tbody>
            </table>
          </section>
        )}
      </div>
    </>
  );
}
