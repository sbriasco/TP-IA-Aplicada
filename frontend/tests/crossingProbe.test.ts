import { expect, it } from "vitest";
import { probeCrossing } from "../src/editor/crossingProbe";

const line = { start: [0, 0.5] as [number, number], end: [1, 0.5] as [number, number] };

it("marca entrada cuando el recorrido sigue la flecha", () => {
  const reading = probeCrossing([0.5, 0.8], [0.5, 0.2], line.start, line.end, "a_to_b");
  expect(reading.label).toBe("Entrada");
});

it("marca salida cuando el recorrido va contra la flecha", () => {
  const reading = probeCrossing([0.5, 0.8], [0.5, 0.2], line.start, line.end, "b_to_a");
  expect(reading.label).toBe("Salida");
});

it("no cuenta un punto apoyado en la línea", () => {
  const reading = probeCrossing([0.5, 0.8], [0.5, 0.5], line.start, line.end, "a_to_b");
  expect(reading.label).toBe("Sobre la línea");
});

it("avisa si la zona no tiene línea", () => {
  expect(probeCrossing([0.2, 0.2], [0.8, 0.8], null, null, null).label).toBe("Sin línea");
});
