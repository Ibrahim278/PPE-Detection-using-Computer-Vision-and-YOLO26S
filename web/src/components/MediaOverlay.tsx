import { useEffect, useRef } from "react";

import type { Box, Worker } from "../lib/api";
import { drawDetections } from "../lib/draw";

/** Canvas that sits exactly on top of a media element (img/video with object-contain) and draws boxes. */
export function useOverlay(
  target: React.RefObject<HTMLElement | null>,
  srcW: number,
  srcH: number,
  workers: Worker[],
  unverified: Box[],
  showIds = true,
) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const el = target.current;
    const c = canvas.current;
    if (!el || !c) return;
    const draw = () => drawDetections(c, el.clientWidth, el.clientHeight, srcW, srcH, workers, unverified, { showIds });
    draw();
    const ro = new ResizeObserver(draw);
    ro.observe(el);
    return () => ro.disconnect();
  }, [target, srcW, srcH, workers, unverified, showIds]);
  return canvas;
}

export function ImageWithOverlay({ src, width, height, workers, unverified }: {
  src: string; width: number; height: number; workers: Worker[]; unverified: Box[];
}) {
  const img = useRef<HTMLImageElement>(null);
  const canvas = useOverlay(img, width, height, workers, unverified);
  return (
    <div className="relative overflow-hidden rounded-lg bg-black">
      <img ref={img} src={src} alt="Analysed image" className="block max-h-[70vh] w-full object-contain" />
      <canvas ref={canvas} className="pointer-events-none absolute inset-0 size-full" aria-hidden />
    </div>
  );
}
