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
  it("muestra las etapas, las tasas por par y el aviso de precisión", async () => {
    const container = document.createElement("div");
    const root = createRoot(container);
    try {
      await act(async () => root.render(<FunnelPanel funnel={funnel} officialEntries={6} />));
      const text = container.textContent ?? "";
      expect(text).toContain("Paso observado");
      expect(text).toContain("Exposición a la vidriera");
      expect(text).toContain("Detención frente a la vidriera");
      expect(text).toContain("Atención estimada");
      expect(text).toContain("Ingreso vinculado");
      expect(text).toContain("No es el total de entradas ni una compra.");
      expect(text).toContain("Umbral: 3 s de video.");
      expect(text).toContain("Umbral: 8 s de video.");
      expect(text).toContain("Estimación. No afirma que haya mirado la vidriera.");
      expect(text).toContain("De paso observado a exposición");
      expect(text).toContain("De exposición a detención");
      expect(text).toContain("De detención a atención estimada");
      expect(text).toContain("De atención estimada a ingreso vinculado");
      expect(text).toContain("La precisión de estas etapas no está comprometida.");
      expect(text).toContain("2 visitas estuvieron en la vidriera y no pasaron por el frente. Quedan fuera del funnel.");
      expect(text).toContain("Ingresos oficiales: 6");
      expect(text).toContain("no disponible");
      expect(text.toLowerCase()).not.toContain("tasa de ingreso");
      const unavailable = Array.from(container.querySelectorAll("li")).find((item) =>
        item.textContent?.includes("De exposición a detención"),
      );
      expect(unavailable?.textContent).toContain("no disponible");
      expect(unavailable?.textContent).not.toContain("0 %");
    } finally {
      await act(async () => root.unmount());
    }
  });

  it("sin vidriera explica la etapa no disponible", async () => {
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
      await act(async () => root.render(<FunnelPanel funnel={withoutShowcase} officialEntries={null} />));
      expect(container.textContent).toContain("No hay zona de vidriera.");
      expect(container.textContent).toContain("No es el total de entradas ni una compra.");
      expect(container.textContent).toContain("Paso observado");
      expect(container.textContent).not.toContain("visitas estuvieron en la vidriera");
    } finally {
      await act(async () => root.unmount());
    }
  });
});
