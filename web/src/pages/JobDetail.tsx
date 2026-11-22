import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Download, ShieldCheck, Trash2, XCircle } from "lucide-react";
import { useMemo, useRef } from "react";
import { Area, AreaChart, CartesianGrid, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Link, useNavigate, useParams } from "react-router";

import { EventList } from "../components/EventList";
import { EmptyState, ErrorBox, PageHeader, ProgressBar, Spinner, StatCard } from "../components/ui";
import { ACTIVE_STATUSES, api, mediaUrl } from "../lib/api";
import { clock, shortName } from "../lib/format";
import { JobStatusPill } from "./Analyze";

const STEPS = ["queued", "downloading", "processing", "done"] as const;

export default function JobDetail() {
  const { id = "" } = useParams();
  const nav = useNavigate();
  const qc = useQueryClient();
  const video = useRef<HTMLVideoElement>(null);

  const job = useQuery({
    queryKey: ["job", id], queryFn: () => api.job(id),
    refetchInterval: (q) => (q.state.data && ACTIVE_STATUSES.includes(q.state.data.status) ? 1000 : false),
  });
  const j = job.data;
  const finished = j && !ACTIVE_STATUSES.includes(j.status);
  const timeline = useQuery({ queryKey: ["timeline", id], queryFn: () => api.timeline(id), enabled: !!finished && j?.status !== "failed" });

  const cancel = useMutation({ mutationFn: () => api.cancelJob(id), onSuccess: () => qc.invalidateQueries({ queryKey: ["job", id] }) });
  const remove = useMutation({
    mutationFn: () => api.deleteJob(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["jobs"] }); nav("/analyze"); },
  });

  const seek = (t: number) => {
    const v = video.current;
    if (!v) return;
    v.currentTime = Math.max(0, t - 0.5);
    v.play().catch(() => {});
    v.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  const chartData = useMemo(() => timeline.data?.map((p) => ({ ...p, ok: p.compliant, bad: p.violations })) ?? [], [timeline.data]);

  if (job.isLoading) return <Spinner label="Loading…" />;
  if (job.error) return <><BackLink /><ErrorBox error={job.error} /></>;
  if (!j) return null;

  const offset = j.start_s ?? 0; // timeline/event times are relative to the analysed section
  const stepIdx = STEPS.indexOf(j.status as (typeof STEPS)[number]);

  return (
    <>
      <BackLink />
      <PageHeader title={shortName(j.source_name, 60)}
        subtitle={`${j.source_type === "url" ? "Link" : "Upload"}${j.start_s != null || j.end_s != null
          ? ` · section ${clock(j.start_s ?? 0)}–${j.end_s != null ? clock(j.end_s) : "end"}` : ""}`}
        actions={
          <div className="flex items-center gap-2">
            <JobStatusPill job={j} />
            {ACTIVE_STATUSES.includes(j.status)
              ? <button className="btn-ghost" onClick={() => cancel.mutate()} disabled={cancel.isPending}><XCircle size={16} aria-hidden /> Cancel</button>
              : <button className="btn-danger" onClick={() => { if (confirm("Delete this video, its results and events?")) remove.mutate(); }}
                  disabled={remove.isPending}><Trash2 size={16} aria-hidden /> Delete</button>}
          </div>
        } />
      <ErrorBox error={cancel.error || remove.error} />

      {ACTIVE_STATUSES.includes(j.status) && (
        <div className="card mb-6 space-y-4 p-5">
          <ol className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
            {STEPS.slice(0, 3).map((s, i) => (
              <li key={s} className={`capitalize ${i < stepIdx ? "text-ok" : i === stepIdx ? "font-medium text-brand" : "text-muted"}`}>
                {i + 1}. {s === "downloading" && j.source_type === "upload" ? "uploaded" : s}
              </li>
            ))}
          </ol>
          <ProgressBar value={j.status === "processing" ? j.progress ?? 0 : 0.02} />
          <p className="text-sm text-muted">
            {j.status === "processing" ? `Tracking workers… ${Math.round((j.progress ?? 0) * 100)}%`
              : j.status === "downloading" ? "Downloading the video…" : "Waiting for the previous video to finish…"}
          </p>
        </div>
      )}

      {j.status === "failed" && <ErrorBox error={j.error ?? "Processing failed."} />}

      {finished && j.summary && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard label="Violations" value={j.summary.violations} tone={j.summary.violations ? "bad" : "ok"} />
            <StatCard label="Peak workers" value={j.summary.peak_workers_in_frame} hint="in one frame" />
            <StatCard label="Length" value={clock(j.summary.video_seconds)} hint={`${j.summary.frames_processed} frames`} />
            <StatCard label="Speed" value={j.summary.pipeline_fps ? `${j.summary.pipeline_fps} fps` : "–"} hint="detection + tracking" />
          </div>

          <div className="grid gap-6 xl:grid-cols-[1fr_360px]">
            <div className="space-y-4">
              {j.video_url && (
                <div className="card overflow-hidden">
                  <video ref={video} src={mediaUrl(j.video_url)} controls playsInline className="block max-h-[65vh] w-full bg-black" />
                  <div className="flex items-center justify-between px-4 py-2 text-xs text-muted">
                    <span>Boxes and the counter are drawn into the video.</span>
                    <a className="inline-flex items-center gap-1 hover:text-ink" href={mediaUrl(j.video_url)} download={`${j.id}_annotated.mp4`}>
                      <Download size={14} aria-hidden /> MP4
                    </a>
                  </div>
                </div>
              )}
              <div className="card p-4">
                <h2 className="mb-1 text-sm font-semibold">Workers over time</h2>
                <p className="mb-3 text-xs text-muted">Red bands mark violations; click one in the list to jump there.</p>
                {timeline.isLoading ? <Spinner /> : chartData.length ? (
                  <div className="h-56" role="img" aria-label="Chart of compliant workers and violations over time">
                    <ResponsiveContainer>
                      <AreaChart data={chartData} margin={{ left: -20, right: 8, top: 4 }}
                        onClick={(e) => { if (e?.activeLabel != null) seek(Number(e.activeLabel)); }}>
                        <CartesianGrid stroke="var(--color-line)" strokeDasharray="3 3" vertical={false} />
                        <XAxis dataKey="t" type="number" domain={["dataMin", "dataMax"]} tickFormatter={(t) => clock(t + offset)}
                          stroke="var(--color-muted)" fontSize={11} />
                        <YAxis allowDecimals={false} stroke="var(--color-muted)" fontSize={11} />
                        <Tooltip contentStyle={{ background: "var(--color-panel)", border: "1px solid var(--color-line)", borderRadius: 8 }}
                          labelFormatter={(t) => clock(Number(t) + offset)} />
                        {j.events?.map((e) => (
                          <ReferenceArea key={e.id} x1={e.started_at_s} x2={e.ended_at_s ?? e.started_at_s + 0.5}
                            fill="var(--color-bad)" fillOpacity={0.15} />
                        ))}
                        <Area type="stepAfter" dataKey="ok" name="Compliant" stroke="var(--color-ok)" fill="var(--color-ok)" fillOpacity={0.15} isAnimationActive={false} />
                        <Area type="stepAfter" dataKey="bad" name="Violations" stroke="var(--color-bad)" fill="var(--color-bad)" fillOpacity={0.3} isAnimationActive={false} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                ) : <p className="text-sm text-muted">No timeline data.</p>}
              </div>
            </div>
            <div className="card h-fit">
              <h2 className="border-b border-line px-4 py-3 text-sm font-semibold">Violations ({j.events?.length ?? 0})</h2>
              {j.events?.length
                ? <EventList events={j.events} onSelect={(e) => seek(e.started_at_s)} timeOffset={offset} />
                : <EmptyState icon={ShieldCheck} title="No violations">Everyone tracked in this video wore a helmet.</EmptyState>}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function BackLink() {
  return (
    <Link to="/analyze" className="mb-4 inline-flex items-center gap-1 text-sm text-muted hover:text-ink">
      <ArrowLeft size={14} aria-hidden /> Analyze
    </Link>
  );
}
