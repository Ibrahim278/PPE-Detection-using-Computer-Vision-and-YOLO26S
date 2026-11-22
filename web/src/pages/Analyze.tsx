import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Clock, FileVideo, Image as ImageIcon, Link2, ListVideo } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";

import { ImageWithOverlay } from "../components/MediaOverlay";
import { ComplianceCounter, Dropzone, EmptyState, ErrorBox, PageHeader, ProgressBar, Spinner, StatusPill } from "../components/ui";
import { ACTIVE_STATUSES, api, type ImageResult, type Job } from "../lib/api";
import { STATUS_LABEL } from "../lib/draw";
import { ago, shortName } from "../lib/format";

type Tab = "image" | "video" | "url";
const TABS: { id: Tab; label: string; icon: typeof ImageIcon }[] = [
  { id: "image", label: "Image", icon: ImageIcon },
  { id: "video", label: "Video file", icon: FileVideo },
  { id: "url", label: "Video link", icon: Link2 },
];

export default function Analyze() {
  const [tab, setTab] = useState<Tab>("image");
  return (
    <>
      <PageHeader title="Analyze" subtitle="Check a photo instantly, or run a video through tracking and violation detection." />
      <div className="grid gap-6 xl:grid-cols-[1fr_340px]">
        <section className="card p-4 md:p-5">
          <div role="tablist" className="mb-5 flex gap-1 rounded-lg bg-panel-2 p-1">
            {TABS.map(({ id, label, icon: Icon }) => (
              <button key={id} role="tab" aria-selected={tab === id} onClick={() => setTab(id)}
                className={`flex flex-1 items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition
                  ${tab === id ? "bg-panel text-ink shadow-sm" : "text-muted hover:text-ink"}`}>
                <Icon size={16} aria-hidden /> {label}
              </button>
            ))}
          </div>
          {tab === "image" && <ImageTab />}
          {tab === "video" && <VideoTab />}
          {tab === "url" && <UrlTab />}
        </section>
        <RecentJobs />
      </div>
    </>
  );
}

function ImageTab() {
  const [preview, setPreview] = useState<string | null>(null);
  const m = useMutation({ mutationFn: api.detectImage });
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  const onFile = (f: File) => {
    setPreview(URL.createObjectURL(f));
    m.mutate(f);
  };
  const r: ImageResult | undefined = m.data;
  return (
    <div className="space-y-4">
      <Dropzone accept="image/jpeg,image/png,image/webp,image/bmp" onFile={onFile} disabled={m.isPending}
        hint="JPEG, PNG or WebP · up to 15 MB" />
      <ErrorBox error={m.error} />
      {m.isPending && <Spinner label="Detecting…" />}
      {r && preview && (
        <>
          <ComplianceCounter summary={r.summary} compact />
          <ImageWithOverlay src={preview} width={r.width} height={r.height} workers={r.workers} unverified={r.unverified} />
          <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
            {r.workers.map((w) => (
              <StatusPill key={w.id} status={w.status}>#{w.id} {STATUS_LABEL[w.status]} · {(w.conf * 100).toFixed(0)}%</StatusPill>
            ))}
            {r.unverified.length > 0 && <StatusPill status="unverified">{r.unverified.length} head not visible</StatusPill>}
            <span className="ml-auto tabular">{r.width}×{r.height} · {r.inference_ms} ms</span>
          </div>
          <p className="text-xs text-muted">Single images are judged frame by frame: any bare head counts as a violation.
            Videos use tracking and smoothing, so brief misdetections don't raise alerts.</p>
        </>
      )}
    </div>
  );
}

function SectionInputs({ start, end, setStart, setEnd }: { start: string; end: string; setStart: (v: string) => void; setEnd: (v: string) => void }) {
  return (
    <fieldset className="grid grid-cols-2 gap-3">
      <legend className="label mb-2 flex items-center gap-1.5"><Clock size={12} aria-hidden /> Section (optional)</legend>
      <div>
        <label htmlFor="start" className="sr-only">Start</label>
        <input id="start" className="input tabular" placeholder="Start, e.g. 3:45" value={start} onChange={(e) => setStart(e.target.value)} />
      </div>
      <div>
        <label htmlFor="end" className="sr-only">End</label>
        <input id="end" className="input tabular" placeholder="End, e.g. 4:15" value={end} onChange={(e) => setEnd(e.target.value)} />
      </div>
    </fieldset>
  );
}

function useCreateJob() {
  const nav = useNavigate();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.createJob,
    onSuccess: (job) => { qc.invalidateQueries({ queryKey: ["jobs"] }); nav(`/jobs/${job.id}`); },
  });
}

function VideoTab() {
  const [file, setFile] = useState<File | null>(null);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const m = useCreateJob();
  return (
    <div className="space-y-4">
      <Dropzone accept="video/*,.mkv,.avi" onFile={setFile} disabled={m.isPending}
        hint="MP4, MOV, AVI, MKV or WebM · up to 500 MB · up to 10 min (or pick a section)" />
      {file && <div className="flex items-center gap-2 text-sm"><FileVideo size={16} className="text-muted" aria-hidden />
        {shortName(file.name)} <span className="text-muted">· {(file.size / 1e6).toFixed(1)} MB</span></div>}
      <SectionInputs {...{ start, end, setStart, setEnd }} />
      <ErrorBox error={m.error} />
      <button className="btn-primary w-full" disabled={!file || m.isPending}
        onClick={() => file && m.mutate({ file, start, end })}>
        {m.isPending ? <Spinner label="Uploading…" /> : "Analyze video"}
      </button>
    </div>
  );
}

function UrlTab() {
  const [url, setUrl] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const m = useCreateJob();
  return (
    <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); if (url.trim()) m.mutate({ url: url.trim(), start, end }); }}>
      <div>
        <label htmlFor="url" className="label">Video link</label>
        <input id="url" className="input" type="url" required placeholder="https://www.youtube.com/watch?v=…  or  https://…/clip.mp4"
          value={url} onChange={(e) => setUrl(e.target.value)} />
        <p className="mt-1.5 text-xs text-muted">Direct video files, YouTube or Vimeo. For long videos, pick a section: only that part is downloaded.</p>
      </div>
      <SectionInputs {...{ start, end, setStart, setEnd }} />
      <ErrorBox error={m.error} />
      <button className="btn-primary w-full" disabled={!url.trim() || m.isPending} type="submit">
        {m.isPending ? <Spinner label="Starting…" /> : "Analyze link"}
      </button>
    </form>
  );
}

export function JobStatusPill({ job }: { job: Job }) {
  const map: Record<Job["status"], string> = {
    queued: "text-muted border-line", downloading: "text-brand border-brand/40", processing: "text-brand border-brand/40",
    done: "text-ok border-ok/40", failed: "text-bad border-bad/40", cancelled: "text-muted border-line",
  };
  return <span className={`rounded-full border px-2 py-0.5 text-xs font-medium capitalize ${map[job.status]}`}>{job.status}</span>;
}

function RecentJobs() {
  const q = useQuery({
    queryKey: ["jobs"], queryFn: api.jobs,
    refetchInterval: (query) => (query.state.data?.some((j) => ACTIVE_STATUSES.includes(j.status)) ? 1500 : false),
  });
  return (
    <aside className="card h-fit">
      <h2 className="border-b border-line px-4 py-3 text-sm font-semibold">Recent videos</h2>
      {q.isLoading && <div className="p-4"><Spinner label="Loading…" /></div>}
      <ErrorBox error={q.error} />
      {q.data?.length === 0 && <EmptyState icon={ListVideo} title="No videos yet">Upload a video or paste a link to start.</EmptyState>}
      <ul className="divide-y divide-line">
        {q.data?.map((j) => (
          <li key={j.id}>
            <Link to={`/jobs/${j.id}`} className="block px-4 py-3 hover:bg-panel-2">
              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-sm font-medium" title={j.source_name}>{shortName(j.source_name, 34)}</span>
                <JobStatusPill job={j} />
              </div>
              <div className="mt-1 flex items-center gap-2 text-xs text-muted">
                <span>{ago(j.created_at)}</span>
                {j.summary && <span>· {j.summary.violations} violation{j.summary.violations === 1 ? "" : "s"}</span>}
              </div>
              {ACTIVE_STATUSES.includes(j.status) && <div className="mt-2"><ProgressBar value={j.progress ?? 0} /></div>}
            </Link>
          </li>
        ))}
      </ul>
    </aside>
  );
}
