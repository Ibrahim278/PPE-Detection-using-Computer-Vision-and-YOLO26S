export const pct = (v: number | undefined | null, digits = 1) =>
  v == null ? "–" : `${(v * 100).toFixed(digits)}%`;

export const num = (v: number | undefined | null, digits = 3) => (v == null ? "–" : v.toFixed(digits));

export function clock(seconds: number | null | undefined) {
  if (seconds == null || !isFinite(seconds)) return "–";
  const s = Math.max(0, seconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = Math.floor(s % 60);
  return h ? `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}` : `${m}:${String(sec).padStart(2, "0")}`;
}

export const duration = (s: number | null | undefined) => (s == null ? "–" : s < 60 ? `${s.toFixed(1)} s` : clock(s));

export function ago(iso: string) {
  const d = (Date.now() - new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z").getTime()) / 1000;
  if (d < 60) return "just now";
  if (d < 3600) return `${Math.floor(d / 60)} min ago`;
  if (d < 86400) return `${Math.floor(d / 3600)} h ago`;
  return new Date(iso).toLocaleDateString();
}

export const shortName = (s: string, max = 48) => (s.length > max ? `${s.slice(0, max - 1)}…` : s);
