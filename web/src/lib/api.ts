// Typed client for the FastAPI backend (api/). In dev, Vite proxies /api and /media.
const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "";

export const mediaUrl = (path: string | null | undefined) => (path ? `${BASE}${path}` : undefined);

export function streamUrl(source = "webcam") {
  const origin = BASE || window.location.origin;
  return `${origin.replace(/^http/, "ws")}/api/stream?source=${encodeURIComponent(source)}`;
}

export type Status = "compliant" | "at_risk" | "violation";
export type Box = [number, number, number, number];

export interface Worker {
  id: number;
  status: Status;
  box: Box;
  conf: number;
  violation_s: number;
  person_box: Box | null;
}

export interface Summary {
  workers: number;
  compliant: number;
  at_risk: number;
  violations: number;
  unverified: number;
}

export interface ImageResult {
  filename: string;
  width: number;
  height: number;
  inference_ms: number;
  summary: Summary;
  workers: Worker[];
  unverified: Box[];
}

export interface ViolationEvent {
  id: number;
  source: "job" | "stream";
  source_id: string;
  event_id: number;
  worker_id: number;
  started_at_s: number;
  ended_at_s: number | null;
  duration_s: number | null;
  end_reason: string | null;
  conf: number | null;
  box: Box | null;
  snapshot_url: string | null;
  status: "open" | "closed";
  created_at: string;
}

export type JobStatus = "queued" | "downloading" | "processing" | "done" | "failed" | "cancelled";

export interface Job {
  id: string;
  created_at: string;
  finished_at: string | null;
  source_type: "upload" | "url";
  source_name: string;
  start_s: number | null;
  end_s: number | null;
  status: JobStatus;
  progress: number | null;
  error: string | null;
  video_url: string | null;
  summary: {
    frames_processed: number;
    video_seconds: number;
    pipeline_fps: number | null;
    violations: number;
    peak_workers_in_frame: number;
    peak_violations_in_frame: number;
    width: number;
    height: number;
    fps: number;
  } | null;
  events?: ViolationEvent[];
}

export interface TimelinePoint extends Summary {
  t: number;
}

export interface EventsSummary {
  total: number;
  open: number;
  last_24h: number;
  by_source: Record<string, number>;
  avg_duration_s: number | null;
}

interface ClassMetrics { precision: number; recall: number; mAP50: number; "mAP50-95": number }
export interface Metrics {
  mAP50: number;
  "mAP50-95": number;
  precision: number;
  recall: number;
  per_class: Record<string, ClassMetrics>;
}
export interface ModelInfo {
  ppe_model: string;
  person_model: string | null;
  classes: string[];
  thresholds: Record<string, number>;
  device: string;
  imgsz: number;
  smoothing: { min_violation_s: number; resolve_s: number; lost_s: number; ema_alpha: number };
  test_metrics?: Metrics;
  baseline_v2?: Metrics;
  benchmark?: { weights: string; device: string; median_ms: number; p95_ms: number; fps: number }[];
}

// Stream messages
export interface StreamReady { type: "ready"; session_id: string; thresholds: Record<string, number> }
export interface StreamEvent {
  type: "violation_started" | "violation_ended";
  event_id: number;
  worker_id: number;
  t: number;
  started_at: number;
  duration_s: number;
  reason: string | null;
  snapshot_url: string | null;
}
export interface StreamFrame {
  type: "frame";
  frame_id: number;
  width: number;
  height: number;
  t: number;
  latency_ms: number;
  dropped: number;
  summary: Summary;
  workers: Worker[];
  unverified: Box[];
  events: StreamEvent[];
}
export interface StreamError { type: "error"; message: string; frame_id?: number }
export type StreamMessage = StreamReady | StreamFrame | StreamError;

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, init);
  } catch {
    throw new ApiError(0, "Can't reach the API server. Is it running on port 8000?");
  }
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") msg = body.detail;
      else if (Array.isArray(body.detail)) msg = body.detail.map((d: { msg: string }) => d.msg).join("; ");
    } catch { /* not JSON */ }
    throw new ApiError(res.status, msg);
  }
  return (res.status === 204 ? undefined : await res.json()) as T;
}

export const api = {
  model: () => request<ModelInfo>("/api/model"),
  detectImage: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<ImageResult>("/api/detect/image", { method: "POST", body: fd });
  },
  createJob: (src: { file?: File; url?: string; start?: string; end?: string }) => {
    const fd = new FormData();
    if (src.file) fd.append("file", src.file);
    if (src.url) fd.append("url", src.url);
    if (src.start) fd.append("start", src.start);
    if (src.end) fd.append("end", src.end);
    return request<Job>("/api/jobs", { method: "POST", body: fd });
  },
  jobs: () => request<Job[]>("/api/jobs?limit=20"),
  job: (id: string) => request<Job>(`/api/jobs/${id}`),
  timeline: (id: string) => request<TimelinePoint[]>(`/api/jobs/${id}/timeline?max_points=600`),
  cancelJob: (id: string) => request<unknown>(`/api/jobs/${id}/cancel`, { method: "POST" }),
  deleteJob: (id: string) => request<void>(`/api/jobs/${id}`, { method: "DELETE" }),
  events: (params: Record<string, string | number | undefined> = {}) => {
    const q = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== "")
      .map(([k, v]) => [k, String(v)]));
    return request<ViolationEvent[]>(`/api/events?${q}`);
  },
  eventsSummary: () => request<EventsSummary>("/api/events/summary"),
};

export const ACTIVE_STATUSES: JobStatus[] = ["queued", "downloading", "processing"];
