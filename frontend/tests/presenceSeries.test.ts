import { describe, expect, it } from "vitest";

import { presenceSeries } from "../src/flow/presenceSeries";

describe("presenceSeries", () => {
  it("sube mientras el track está en la zona frontal y baja al salir", () => {
    const series = presenceSeries(
      [
        { kind: "zone_enter", zone_role: "front", track_id: 1, video_timestamp_seconds: 0 },
        { kind: "zone_exit", zone_role: "front", track_id: 1, video_timestamp_seconds: 3 },
        { kind: "zone_enter", zone_role: "front", track_id: 2, video_timestamp_seconds: 2 },
        { kind: "zone_exit", zone_role: "front", track_id: 2, video_timestamp_seconds: 4 },
      ],
      0,
      4,
    );
    expect(series.map((point) => point.track_count)).toEqual([1, 1, 2, 1, 0]);
  });

  it("no deja al track en la zona si se pierde el seguimiento", () => {
    const series = presenceSeries(
      [{ kind: "zone_enter", zone_role: "front", track_id: 4, video_timestamp_seconds: 2.2 }],
      0,
      4,
    );
    expect(series.find((point) => point.seconds === 2)?.track_count).toBe(1);
    expect(series.find((point) => point.seconds === 3)?.track_count).toBe(0);
  });
});
