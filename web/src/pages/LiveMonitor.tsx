import { Camera, CircleStop, FileVideo, Play, ShieldAlert, ShieldCheck } from "lucide-react";
import { useRef, useState } from "react";

import { Sparkline } from "../components/charts";
import { useOverlay } from "../components/MediaOverlay";
import { ComplianceCounter, EmptyState, ErrorBox, PageHeader, Spinner } from "../components/ui";
import { mediaUrl } from "../lib/api";
import { duration } from "../lib/format";
import { MIN_TRACKING_FPS, useLiveStream } from "../lib/useLiveStream";

const REASON: Record<string, string> = { helmet_on: "helmet put on", lost: "left view", stopped: "stream stopped" };
const EMPTY: never[] = [];

export default function LiveMonitor() {
  const video = useRef<HTMLVideoElement>(null);
  const live = useLiveStream(video);
  const [mode, setMode] = useState<"webcam" | "file">("webcam");
  const [file, setFile] = useState<File | null>(null);
  const [showIds, setShowIds] = useState(true);
  const f = live.frame;
  const overlay = useOverlay(video, f?.width ?? 0, f?.height ?? 0, f?.workers ?? EMPTY, f?.unverified ?? EMPTY, showIds);
  const running = live.status === "live" || live.status === "starting";
  const open = live.feed.filter((x) => x.status === "open").length;

  return (
    <>
      <PageHeader title="Live Monitor" subtitle="Watch a camera in real time. Workers are tracked, and an alert fires after a bare head persists for about 1.5 s." />

      <div className="card mb-4 flex flex-wrap items-center gap-3 p-3">
        <div role="radiogroup" aria-label="Source" className="flex gap-1 rounded-lg bg-panel-2 p-1">
          {([["webcam", "Webcam", Camera], ["file", "Video file", FileVideo]] as const).map(([id, label, Icon]) => (
            <button key={id} role="radio" aria-checked={mode === id} disabled={running} onClick={() => setMode(id)}
              className={`flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition disabled:opacity-60
                ${mode === id ? "bg-panel text-ink shadow-sm" : "text-muted hover:text-ink"}`}>
              <Icon size={15} aria-hidden /> {label}
            </button>
          ))}
        </div>
        {mode === "file" && (
          <label className="btn-ghost cursor-pointer">
            <FileVideo size={15} aria-hidden /> {file ? file.name.slice(0, 28) : "Choose video…"}
            <input type="file" accept="video/*,.avi,.mkv" className="hidden" disabled={running}
              onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          </label>
        )}
        {running
          ? <button className="btn-danger" onClick={live.stop}><CircleStop size={16} aria-hidden /> Stop</button>
          : <button className="btn-primary" disabled={mode === "file" && !file}
              onClick={() => live.start(mode === "webcam" ? { kind: "webcam" } : { kind: "file", file: file! })}>
              <Play size={16} aria-hidden /> Start
            </button>}
        <label className="ml-auto flex items-center gap-2 text-sm text-muted">
          <input type="checkbox" checked={showIds} onChange={(e) => setShowIds(e.target.checked)} className="accent-[var(--color-brand)]" />
          Show IDs
        </label>
        <LiveBadge status={live.status} fps={live.stats.fps} latency={live.stats.latency} />
      </div>

      <div className="mb-4 space-y-2">
        <ErrorBox error={live.error} />
        {live.status === "live" && live.stats.fps > 0 && live.stats.fps < MIN_TRACKING_FPS && (
          <div role="status" className="rounded-lg border border-risk/40 bg-risk/10 px-3 py-2 text-sm text-risk">
            Low frame rate ({live.stats.fps.toFixed(0)} fps). Tracking needs about {MIN_TRACKING_FPS} fps or more, so workers may not
            be picked up. Keep this tab visible and in front; background tabs are slowed down by the browser.
          </div>
        )}
      </div>

      <div className="mb-4"><ComplianceCounter summary={f?.summary ?? null} compact /></div>
      {(running || live.trend.points.length > 0) && (
        <div className="mb-4 grid gap-3 sm:grid-cols-2">
          <Sparkline data={live.trend.points} now={live.trend.now} dataKey="workers" label="Workers" color="var(--color-chart)" />
          <Sparkline data={live.trend.points} now={live.trend.now} dataKey="violations" label="Violations" color="var(--color-bad)" />
        </div>
      )}

      <div className="grid gap-4 xl:grid-cols-[1fr_340px]">
        <div className="card relative aspect-video overflow-hidden bg-black">
          <video ref={video} playsInline muted className="absolute inset-0 size-full object-contain" />
          <canvas ref={overlay} className="pointer-events-none absolute inset-0 size-full" aria-hidden />
          {live.status === "idle" && !live.error && (
            <div className="absolute inset-0 grid place-items-center">
              <EmptyState icon={Camera} title="Not monitoring">
                Pick a source and press Start. “Video file” plays a recording as if it were a camera.
              </EmptyState>
            </div>
          )}
          {live.status === "starting" && <div className="absolute inset-0 grid place-items-center"><Spinner label="Starting…" /></div>}
        </div>

        <aside className="card flex max-h-[70vh] flex-col">
          <div className="flex items-center justify-between border-b border-line px-4 py-3">
            <h2 className="text-sm font-semibold">Violation feed</h2>
            {open > 0 && <span className="rounded-full bg-bad px-2 py-0.5 text-xs font-semibold text-white">{open} active</span>}
          </div>
          {live.feed.length === 0
            ? <EmptyState icon={ShieldCheck} title="No violations">Alerts show up here with a snapshot of the worker.</EmptyState>
            : (
              <ul className="divide-y divide-line overflow-y-auto" aria-live="polite">
                {live.feed.map((it) => (
                  <li key={it.eventId} className="flex gap-3 px-4 py-3">
                    {it.snapshotUrl
                      ? <img src={mediaUrl(it.snapshotUrl)} alt={`Worker ${it.workerId} without a helmet`} className="h-20 w-16 shrink-0 rounded-md bg-black object-cover" />
                      : <div className="grid h-20 w-16 shrink-0 place-items-center rounded-md bg-panel-2"><ShieldAlert size={18} className="text-bad" aria-hidden /></div>}
                    <div className="min-w-0 text-sm">
                      <div className="font-medium">Worker #{it.workerId} · no helmet</div>
                      <div className="text-muted">{it.startedAt.toLocaleTimeString()}</div>
                      {it.status === "open"
                        ? <span className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-bad"><span className="size-1.5 animate-pulse rounded-full bg-bad" /> Active</span>
                        : <span className="text-xs text-muted">Resolved after {duration(it.durationS)} · {REASON[it.reason ?? ""] ?? it.reason}</span>}
                    </div>
                  </li>
                ))}
              </ul>
            )}
        </aside>
      </div>
    </>
  );
}

function LiveBadge({ status, fps, latency }: { status: string; fps: number; latency: number }) {
  if (status !== "live") return null;
  return (
    <span className="tabular inline-flex items-center gap-2 rounded-full border border-bad/40 bg-bad/10 px-2.5 py-1 text-xs font-medium text-bad">
      <span className="size-2 animate-pulse rounded-full bg-bad" aria-hidden /> LIVE
      <span className="text-muted">{fps.toFixed(0)} fps · {latency} ms</span>
    </span>
  );
}
