import type { Box, Status, Worker } from "./api";

// Same meaning as the Python overlay: green = helmet, amber = possibly bare head, red = violation.
const COLORS: Record<Status | "unverified", string> = {
  compliant: "#22c55e",
  at_risk: "#f59e0b",
  violation: "#ef4444",
  unverified: "#94a3b8",
};

export const STATUS_LABEL: Record<Status, string> = {
  compliant: "Helmet",
  at_risk: "No helmet?",
  violation: "No helmet",
};

/** Where an element with `object-fit: contain` actually draws its content. */
export function containRect(boxW: number, boxH: number, srcW: number, srcH: number) {
  const scale = Math.min(boxW / srcW, boxH / srcH);
  const w = srcW * scale;
  const h = srcH * scale;
  return { x: (boxW - w) / 2, y: (boxH - h) / 2, scale };
}

/**
 * Draw detections (in source-pixel coordinates) on a canvas that overlays a
 * media element of size cssW x cssH showing a srcW x srcH source with object-fit: contain.
 */
export function drawDetections(
  canvas: HTMLCanvasElement,
  cssW: number,
  cssH: number,
  srcW: number,
  srcH: number,
  workers: Worker[],
  unverified: Box[],
  opts: { showIds?: boolean } = {},
) {
  const dpr = window.devicePixelRatio || 1;
  if (canvas.width !== Math.round(cssW * dpr) || canvas.height !== Math.round(cssH * dpr)) {
    canvas.width = Math.round(cssW * dpr);
    canvas.height = Math.round(cssH * dpr);
  }
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cssW, cssH);
  if (!srcW || !srcH) return;
  const { x: ox, y: oy, scale } = containRect(cssW, cssH, srcW, srcH);
  const rect = (b: Box) => [ox + b[0] * scale, oy + b[1] * scale, (b[2] - b[0]) * scale, (b[3] - b[1]) * scale] as const;

  ctx.lineWidth = 1;
  ctx.setLineDash([4, 3]);
  ctx.strokeStyle = COLORS.unverified;
  for (const b of unverified) ctx.strokeRect(...rect(b));
  ctx.setLineDash([]);

  ctx.font = "600 12px Inter, system-ui, sans-serif";
  ctx.textBaseline = "bottom";
  for (const w of workers) {
    const color = COLORS[w.status];
    if (w.person_box) {
      ctx.lineWidth = 1;
      ctx.strokeStyle = color + "99";
      ctx.strokeRect(...rect(w.person_box));
    }
    const [x, y, bw, bh] = rect(w.box);
    ctx.lineWidth = 2.5;
    ctx.strokeStyle = color;
    ctx.strokeRect(x, y, bw, bh);

    let label = STATUS_LABEL[w.status];
    if (w.status === "violation" && w.violation_s > 0) label += ` ${w.violation_s.toFixed(1)}s`;
    if (opts.showIds !== false) label = `#${w.id} ${label}`;
    const tw = ctx.measureText(label).width + 8;
    const ly = Math.max(16, y - 2);
    ctx.fillStyle = color;
    ctx.fillRect(x, ly - 16, tw, 16);
    ctx.fillStyle = w.status === "at_risk" ? "#1a1203" : "#ffffff";
    ctx.fillText(label, x + 4, ly - 2);
  }
}
