import { describe, expect, it } from "vitest";

import { visibleBuckets } from "../src/flow/visibleBuckets";

const minutes = [
  { start_seconds: 0, track_count: 2 },
  { start_seconds: 60, track_count: 1 },
  { start_seconds: 120, track_count: 4 },
];

describe("visibleBuckets", () => {
  it("muestra entero el minuto que se solapa y omite el que no", () => {
    expect(visibleBuckets(minutes, 50, 70).map((bucket) => bucket.start_seconds)).toEqual([0, 60]);
    expect(visibleBuckets(minutes, 50, 70)[0]).toEqual(minutes[0]);
  });

  it("no cambia los indicadores de la sesión", () => {
    const indicators = { traffic_total: 3, entry_rate: 0.5 };
    visibleBuckets(minutes, 50, 70);
    expect(indicators).toEqual({ traffic_total: 3, entry_rate: 0.5 });
  });
});
