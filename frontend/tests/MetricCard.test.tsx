import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it } from "vitest";
import { MetricCard } from "../src/components/MetricCard";
import type { MetricValue } from "../src/api/metrics";

describe("MetricCard", () => {
  it.each([
    ["entry_rate", 0.25, "25 %"],
    ["entry_rate", 0, "0 %"],
    ["dwell_mean_seconds", 3.125, "3,13 s"],
    ["traffic_total", 1200, "1.200"],
  ])("presenta %s con la escala y unidad apropiada", async (code, value, expected) => {
    const container = document.createElement("div");
    const root = createRoot(container);
    try {
      const metric: MetricValue = { code, value, availability: "available", label: "none", unavailable_reason: null };
      await act(async () => root.render(<MetricCard metric={metric} />));
      expect(container.textContent).toContain(expected);
    } finally { await act(async () => root.unmount()); }
  });

  it("no convierte una tasa sin denominador en cero", async () => {
    const container = document.createElement("div");
    const root = createRoot(container);
    try {
      await act(async () => root.render(<MetricCard metric={{ code: "entry_rate", value: null, availability: "unavailable", label: "none", unavailable_reason: "no_passes" }} />));
      expect(container.textContent).toContain("no disponible");
      expect(container.textContent).not.toContain("0 %");
      expect(container.textContent).toContain("Sin pasos en el área externa");
    } finally { await act(async () => root.unmount()); }
  });
});
