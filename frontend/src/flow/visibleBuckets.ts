export interface FlowMinute {
  start_seconds: number;
}

const MINUTE_SECONDS = 60;

/** A stored minute is shown whole when it overlaps the chosen range. */
export function visibleBuckets<T extends FlowMinute>(
  buckets: readonly T[],
  fromSeconds: number,
  toSeconds: number,
): T[] {
  return buckets.filter((bucket) => {
    const end = bucket.start_seconds + MINUTE_SECONDS;
    return bucket.start_seconds < toSeconds && end > fromSeconds;
  });
}
