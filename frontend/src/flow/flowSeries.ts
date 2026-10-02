import type { FlowMinute } from "./visibleBuckets";

const MINUTE_SECONDS = 60;

export interface FlowPoint {
  seconds: number;
  track_count: number;
}

/**
 * Turns minute buckets into a timeline inside the selected range.
 * Each count stays flat until the next minute, clipped to the range.
 */
export function flowSeries<T extends FlowMinute & { track_count: number }>(
  buckets: readonly T[],
  fromSeconds: number,
  toSeconds: number,
): FlowPoint[] {
  if (!(toSeconds > fromSeconds)) return [];
  const window = buckets
    .map((bucket) => {
      const start = Math.max(bucket.start_seconds, fromSeconds);
      const end = Math.min(bucket.start_seconds + MINUTE_SECONDS, toSeconds);
      return { start, end, track_count: bucket.track_count };
    })
    .filter((bucket) => bucket.end > bucket.start)
    .sort((left, right) => left.start - right.start);
  if (window.length === 0) return [];
  const points = window.map((bucket) => ({ seconds: bucket.start, track_count: bucket.track_count }));
  const last = window[window.length - 1];
  points.push({ seconds: last.end, track_count: last.track_count });
  return points;
}
