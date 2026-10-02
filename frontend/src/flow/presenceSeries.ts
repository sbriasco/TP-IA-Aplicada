import type { FlowPoint } from "./flowSeries";

export interface PresenceEvent {
  kind: string;
  zone_role: string | null;
  track_id: number;
  video_timestamp_seconds: number;
}

interface Stay {
  start: number;
  end: number;
}

/** Front-zone stays. A track without exit counts only at the instant it was seen. */
export function frontStays(events: readonly PresenceEvent[]): Stay[] {
  const byTrack = new Map<number, PresenceEvent[]>();
  for (const event of events) {
    if (event.zone_role !== "front") continue;
    if (event.kind !== "zone_enter" && event.kind !== "zone_exit") continue;
    const list = byTrack.get(event.track_id) ?? [];
    list.push(event);
    byTrack.set(event.track_id, list);
  }
  const stays: Stay[] = [];
  for (const list of byTrack.values()) {
    list.sort((left, right) => left.video_timestamp_seconds - right.video_timestamp_seconds);
    let open: number | null = null;
    for (const event of list) {
      if (event.kind === "zone_enter") {
        open = event.video_timestamp_seconds;
      } else if (open !== null) {
        stays.push({ start: open, end: event.video_timestamp_seconds });
        open = null;
      }
    }
    if (open !== null) stays.push({ start: open, end: open });
  }
  return stays;
}

function presentAt(stays: readonly Stay[], seconds: number, step: number): number {
  return stays.filter((stay) =>
    stay.end === stay.start
      ? stay.start >= seconds && stay.start < seconds + step
      : stay.start <= seconds && seconds < stay.end,
  ).length;
}

/** How many tracks are in the front zone at each moment of the selected range. */
export function presenceSeries(
  events: readonly PresenceEvent[],
  fromSeconds: number,
  toSeconds: number,
): FlowPoint[] {
  if (!(toSeconds > fromSeconds)) return [];
  const stays = frontStays(events);
  const step = toSeconds - fromSeconds > 180 ? 5 : 1;
  const points: FlowPoint[] = [];
  const seen = new Set<number>();
  for (let cursor = fromSeconds; cursor <= toSeconds + 1e-6; cursor += step) {
    const seconds = Math.min(Math.round(cursor * 1000) / 1000, toSeconds);
    if (seen.has(seconds)) continue;
    seen.add(seconds);
    points.push({ seconds, track_count: presentAt(stays, seconds, step) });
  }
  return points;
}
