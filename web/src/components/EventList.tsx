import { ShieldAlert } from "lucide-react";
import { Link } from "react-router";

import { mediaUrl, type ViolationEvent } from "../lib/api";
import { ago, clock, duration } from "../lib/format";

const REASON: Record<string, string> = { helmet_on: "helmet put on", lost: "left view", stopped: "video ended" };

export function EventList({ events, onSelect, timeOffset = 0, showSource }: {
  events: ViolationEvent[]; onSelect?: (e: ViolationEvent) => void; timeOffset?: number; showSource?: boolean;
}) {
  return (
    <ul className="divide-y divide-line">
      {events.map((e) => {
        const body = (
          <div className="flex gap-3 px-4 py-3">
            {e.snapshot_url
              ? <img src={mediaUrl(e.snapshot_url)} alt={`Worker ${e.worker_id} without a helmet`} loading="lazy"
                  className="h-20 w-16 shrink-0 rounded-md bg-black object-cover" />
              : <div className="grid h-20 w-16 shrink-0 place-items-center rounded-md bg-panel-2"><ShieldAlert size={18} className="text-bad" aria-hidden /></div>}
            <div className="min-w-0 text-sm">
              <div className="font-medium">Worker #{e.worker_id} · no helmet</div>
              <div className="tabular text-muted">
                at {clock(e.started_at_s + timeOffset)} · {e.status === "open" ? <span className="text-bad">ongoing</span> : duration(e.duration_s)}
              </div>
              <div className="text-xs text-muted">
                {e.end_reason && <>ended: {REASON[e.end_reason] ?? e.end_reason}</>}
                {showSource && <> · {e.source === "job" ? "video" : "live"} · {ago(e.created_at)}</>}
              </div>
              {showSource && e.source === "job" && (
                <Link to={`/jobs/${e.source_id}`} className="text-xs text-brand hover:underline">Open video</Link>
              )}
            </div>
          </div>
        );
        return (
          <li key={e.id}>
            {onSelect
              ? <button className="block w-full text-left hover:bg-panel-2" onClick={() => onSelect(e)}>{body}</button>
              : body}
          </li>
        );
      })}
    </ul>
  );
}
