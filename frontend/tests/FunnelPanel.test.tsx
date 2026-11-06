import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it } from "vitest";

import type { ShopFunnel } from "../src/api/funnel";
import { FunnelPanel } from "../src/components/FunnelPanel";

const funnel: ShopFunnel = {
  session_id: "s-1",
  shop_id: "shop-1",
  stop_threshold_seconds: "3",
  attention_threshold_seconds: "8",
  excluded_window_only: 2,
  precision_uncommitted: true,
  stages: [
    { stage: "observed_pass", count: 4, availability: "available", label: "none", unavailable_reason: null },
    { stage: "exposure", count: 3, availability: "available", label: "none", unavailable_reason: null },
    { stage: "stop", count: 2, availability: "available", label: "none", unavailable_reason: null },
    { stage: "attention", count: 1, availability: "available", label: "attention_estimate", unavailable_reason: null },
    { stage: "linked_entry", count: 1, availability: "available", label: "none", unavailable_reason: null },
  ],
  rates: [
    { code: "observed_pass_to_exposure", value: "0.750000", availability: "available", unavailable_reason: null },
    { code: "exposure_to_stop", value: null, availability: "unavailable", unavailable_reason: "no_previous_stage" },
    { code: "stop_to_attention", value: "0.500000", availability: "available", unavailable_reason: null },
    { code: "attention_to_linked_entry", value: "1.000000", availability: "available", unavailable_reason: null },
  ],
};

describe("FunnelPanel", () => {
  it("muestra las etapas sin las tasas", async () => {
    const container = document.createElement("div");
    const root = createRoot(container);
    try {
      await act(async () => root.render(<FunnelPanel funnel={funnel} />));
      const text = container.textContent ?? "";
      expect(text).toContain("Paso observado");
      expect(text).toContain("Con salida observada");
      expect(text).toContain("Detención frente a la vidriera");
      expect(text).toContain("Atención estimada");
      expect(text).toContain("Ingreso vinculado");
      expect(text).not.toContain("No es el total de entradas ni una compra.");
      expect(text).not.toContain("Umbral");
      expect(text).not.toContain("De paso observado a exposición");
      expect(text).not.toContain("De exposición a detención");
      expect(text).not.toContain("De detención a atención estimada");
      expect(text).not.toContain("De atención estimada a ingreso vinculado");
      expect(text).not.toContain("79,5");
      expect(text).not.toContain("%");
      expect(text).not.toContain("precisión");
      expect(text).not.toContain("Quedan fuera del funnel");
      expect(text).not.toContain("Ingresos oficiales");
      expect(text.toLowerCase()).not.toContain("tasa de ingreso");
    } finally {
      await act(async () => root.unmount());
    }
  });

  it("sin vidriera muestra la etapa como no disponible", async () => {
    const container = document.createElement("div");
    const root = createRoot(container);
    const withoutShowcase: ShopFunnel = {
      ...funnel,
      excluded_window_only: 0,
      stages: funnel.stages.map((stage) =>
        stage.stage === "observed_pass"
          ? stage
          : { ...stage, count: null, availability: "unavailable", label: "none", unavailable_reason: "no_showcase" },
      ),
    };
    try {
      await act(async () => root.render(<FunnelPanel funnel={withoutShowcase} />));
      expect(container.textContent).toContain("no disponible");
      expect(container.textContent).not.toContain("No hay zona de vidriera.");
      expect(container.textContent).toContain("Paso observado");
    } finally {
      await act(async () => root.unmount());
    }
  });
});
