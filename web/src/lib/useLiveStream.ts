import { useCallback, useEffect, useRef, useState } from "react";

import type { TrendPoint } from "../components/charts";
import { streamUrl, type StreamEvent, type StreamFrame, type StreamMessage } from "./api";

export type LiveStatus = "idle" | "starting" | "live" | "error";
export type LiveSource = { kind: "webcam" } | { kind: "file"; file: File };

export interface FeedItem {
  eventId: number;
  workerId: number;
  startedAt: Date;
  snapshotUrl: string | null;
  status: "open" | "resolved";
  durationS?: number;
  reason?: string | null;
}

const MAX_FPS = 20;          // frames sent per second (the server drops anything it can't keep up with)
const MAX_IN_FLIGHT = 2;     // keeps the server busy while the next frame is on the wire
export const MIN_TRACKING_FPS = 10; // below this, heads move too far between frames to be tracked
const TREND_WINDOW_S = 60;
const TREND_SAMPLE_MS = 250;         // 4 points/s keeps the sparklines smooth without re-rendering every frame
const MAX_WIDTH = 1280;      // downscale bigger cameras before sending
const JPEG_QUALITY = 0.92;   // heavier compression can hide borderline bare heads

/**
 * Captures frames from a <video> (webcam or a local file played as a camera),
 * sends them over the /api/stream WebSocket and returns the latest result.
 * One frame is in flight at a time, so latency stays at one round trip.
 */
export function useLiveStream(video: React.RefObject<HTMLVideoElement | null>) {
  const [status, setStatus] = useState<LiveStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [frame, setFrame] = useState<StreamFrame | null>(null);
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const [stats, setStats] = useState({ fps: 0, latency: 0 });
  const [trend, setTrend] = useState<{ points: TrendPoint[]; now: number }>({ points: [], now: 0 });
  const trendStart = useRef(0);
  const lastTrend = useRef(0);

  const ws = useRef<WebSocket | null>(null);
  const mediaStream = useRef<MediaStream | null>(null);
  const objectUrl = useRef<string | null>(null);
  const raf = useRef<number>(0);
  const inFlight = useRef(0);
  const lastSent = useRef(0);
  const sentAt = useRef(new Map<number, number>());
  const sentCount = useRef(0);
  const resultTimes = useRef<number[]>([]);
  const canvas = useRef<HTMLCanvasElement | null>(null);

  const cleanup = useCallback(() => {
    cancelAnimationFrame(raf.current);
    ws.current?.close();
    ws.current = null;
    mediaStream.current?.getTracks().forEach((t) => t.stop());
    mediaStream.current = null;
    const v = video.current;
    if (v) { v.pause(); v.srcObject = null; v.removeAttribute("src"); v.load(); }
    if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
    objectUrl.current = null;
    inFlight.current = 0;
    sentAt.current.clear();
  }, [video]);

  const stop = useCallback(() => { cleanup(); setStatus("idle"); setFrame(null); }, [cleanup]);

  const applyEvents = (events: StreamEvent[]) => {
    if (!events.length) return;
    setFeed((prev) => {
      let next = [...prev];
      for (const e of events) {
        if (e.type === "violation_started") {
          next = [{ eventId: e.event_id, workerId: e.worker_id, startedAt: new Date(), snapshotUrl: e.snapshot_url, status: "open" as const }, ...next].slice(0, 50);
        } else {
          next = next.map((f) => (f.eventId === e.event_id ? { ...f, status: "resolved", durationS: e.duration_s, reason: e.reason } : f));
        }
      }
      return next;
    });
  };

  const loop = useCallback(() => {
    raf.current = requestAnimationFrame(loop);
    const v = video.current;
    const sock = ws.current;
    if (!v || !sock || sock.readyState !== WebSocket.OPEN || inFlight.current >= MAX_IN_FLIGHT) return;
    if (v.readyState < 2 || !v.videoWidth) return;
    const now = performance.now();
    if (now - lastSent.current < 1000 / MAX_FPS) return;
    lastSent.current = now;
    inFlight.current += 1;

    const scale = Math.min(1, MAX_WIDTH / v.videoWidth);
    const c = (canvas.current ??= document.createElement("canvas"));
    c.width = Math.round(v.videoWidth * scale);
    c.height = Math.round(v.videoHeight * scale);
    c.getContext("2d")!.drawImage(v, 0, 0, c.width, c.height);
    c.toBlob((blob) => {
      if (!blob || ws.current !== sock || sock.readyState !== WebSocket.OPEN) { inFlight.current = Math.max(0, inFlight.current - 1); return; }
      sentCount.current += 1;
      sentAt.current.set(sentCount.current, performance.now());
      sock.send(blob);
    }, "image/jpeg", JPEG_QUALITY);
  }, [video]);

  const start = useCallback(async (source: LiveSource) => {
    cleanup();
    setError(null);
    setFeed([]);
    setFrame(null);
    setTrend({ points: [], now: 0 });
    setStatus("starting");
    const v = video.current;
    if (!v) return;
    try {
      if (source.kind === "webcam") {
        if (!navigator.mediaDevices?.getUserMedia) {
          throw new Error("This browser can't access a camera here (it needs HTTPS or localhost). Try “Video file” instead.");
        }
        mediaStream.current = await navigator.mediaDevices.getUserMedia({
          video: { width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false,
        });
        v.srcObject = mediaStream.current;
        v.loop = false;
      } else {
        objectUrl.current = URL.createObjectURL(source.file);
        v.src = objectUrl.current;
        v.loop = true;
      }
      v.muted = true;
      await v.play();
    } catch (e) {
      cleanup();
      setStatus("error");
      const name = (e as DOMException)?.name;
      setError(name === "NotAllowedError" ? "Camera permission was denied. Allow camera access, or use “Video file”."
        : name === "NotFoundError" ? "No camera found. Use “Video file” to test with a recording."
        : (e as Error).message || "Could not start the video source.");
      return;
    }

    const sock = new WebSocket(streamUrl(source.kind === "webcam" ? "webcam" : `file:${source.file.name}`.slice(0, 64)));
    sock.binaryType = "arraybuffer";
    ws.current = sock;
    sentCount.current = 0;
    resultTimes.current = [];
    trendStart.current = performance.now();
    lastTrend.current = 0;
    sock.onmessage = (ev) => {
      const msg = JSON.parse(ev.data as string) as StreamMessage;
      if (msg.type === "ready") { setStatus("live"); raf.current = requestAnimationFrame(loop); return; }
      // The server drops stale frames, so a reply means every earlier frame is done too.
      if (msg.type === "error") {
        inFlight.current = 0;
        if (msg.frame_id == null) { setError(msg.message); setStatus("error"); }
        return;
      }
      inFlight.current = 0;
      for (const id of sentAt.current.keys()) if (id < msg.frame_id) sentAt.current.delete(id);
      const now = performance.now();
      const sent = sentAt.current.get(msg.frame_id);
      sentAt.current.delete(msg.frame_id);
      const times = resultTimes.current;
      times.push(now);
      while (times.length && now - times[0] > 2000) times.shift();
      setStats({ fps: times.length / 2, latency: sent ? Math.round(now - sent) : 0 });
      setFrame(msg);
      applyEvents(msg.events);
      if (now - lastTrend.current >= TREND_SAMPLE_MS) {
        lastTrend.current = now;
        const t = (now - trendStart.current) / 1000;
        const point = { t, workers: msg.summary.workers, violations: msg.summary.violations };
        setTrend((prev) => ({ now: t, points: [...prev.points.filter((p) => p.t >= t - TREND_WINDOW_S), point] }));
      }
    };
    sock.onerror = () => { setError("Lost connection to the API server."); };
    sock.onclose = (ev) => {
      if (ws.current !== sock) return; // closed by stop()/restart
      cleanup();
      setStatus(ev.code === 1013 ? "error" : "idle");
      if (ev.code === 1013) setError("The server is busy with other live streams. Try again shortly.");
      else if (ev.code !== 1000) setError("The live connection closed unexpectedly.");
    };
  }, [cleanup, loop, video]);

  useEffect(() => cleanup, [cleanup]);

  return { status, error, frame, feed, stats, trend, start, stop };
}
