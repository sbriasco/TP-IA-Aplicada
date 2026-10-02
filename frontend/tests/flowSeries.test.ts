import { describe, expect, it } from "vitest";

import { flowSeries } from "../src/flow/flowSeries";

const minutes = [
  { start_seconds: 0, track_count: 3 },
  { start_seconds: 60, track_count: 1 },
];

describe("flowSeries", () => {
  it("apoya el conteo sobre el tiempo del video, no en una barra suelta", () => {
    expect(flowSeries(minutes, 0, 15.32)).toEqual([
      { seconds: 0, track_count: 3 },
      { seconds: 15.32, track_count: 3 },
    ]);
  });

  it("cambia de nivel en el minuto siguiente y se corta en el fin del tramo", () => {
    expect(flowSeries(minutes, 0, 90)).toEqual([
      { seconds: 0, track_count: 3 },
      { seconds: 60, track_count: 1 },
      { seconds: 90, track_count: 1 },
    ]);
  });

  it("recorta el inicio cuando el tramo empieza a mitad de un minuto", () => {
    expect(flowSeries(minutes, 50, 70)).toEqual([
      { seconds: 50, track_count: 3 },
      { seconds: 60, track_count: 1 },
      { seconds: 70, track_count: 1 },
    ]);
  });
});
