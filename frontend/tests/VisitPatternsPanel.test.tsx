import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it } from "vitest";

import type { VisitPatterns } from "../src/api/visitPatterns";
import { VisitPatternsPanel } from "../src/components/VisitPatternsPanel";

const shops = [
  { shop_id: "shop-norte", name: "Local Norte" },
  { shop_id: "shop-sur", name: "Local Sur" },
];

const patterns: VisitPatterns = {
  patterns_availability: "available",
  patterns_unavailable_reason: null,
  groups_availability: "available",
  group_count: 1,
  proximity_width_fraction: "0.08",
  direction_degrees: "45",
  minimum_seconds: "2",
  area_transitions: [
    {
      from_shop_id: "shop-norte",
      from_zone_role: "front",
      to_shop_id: "shop-sur",
      to_zone_role: "window",
      track_count: 2,
    },
  ],
  sequences: [
    {
      areas: [
        { shop_id: "shop-norte", zone_role: "front" },
        { shop_id: "shop-norte", zone_role: "interior" },
      ],
      track_count: 1,
    },
  ],
  shop_transitions: [{ from_shop_id: "shop-norte", to_shop_id: "shop-sur", track_count: 2 }],
  groups: [
    {
      ordinal: 1,
      started_video_timestamp_seconds: "1.5",
      ended_video_timestamp_seconds: "4.0",
      label: "group_estimate",
      track_ids: [3, 7],
    },
  ],
  precision_uncommitted: true,
};

describe("VisitPatternsPanel", () => {
  it("muestra recorridos, grupos y el aviso de precisión", async () => {
    const container = document.createElement("div");
    const root = createRoot(container);
    try {
      await act(async () => root.render(<VisitPatternsPanel patterns={patterns} shops={shops} />));
      const text = container.textContent ?? "";
      expect(text).toContain("De Local Norte · frente a Local Sur · vidriera");
      expect(text).toContain("Local Norte · frente → Local Norte · interior");
      expect(text).toContain("De Local Norte a Local Sur");
      expect(text).not.toContain("entrada");
      expect(text).not.toContain("compra");
      expect(text).toContain("Visita 3");
      expect(text).toContain("Visita 7");
      expect(text).toContain("1.5–4.0 s");
      expect(text).toContain("Estimación. No afirma una relación real.");
      expect(text).toContain("ocho centésimas del ancho del encuadre");
      expect(text).toContain("45 grados");
      expect(text).toContain("2 segundos de video");
      expect(text).toContain("La precisión de los patrones y de los grupos estimados no está comprometida.");
      expect(text).not.toContain("0.005");
    } finally {
      await act(async () => root.unmount());
    }
  });

  it("sin áreas conserva los grupos y no reemplaza las listas por cero", async () => {
    const container = document.createElement("div");
    const root = createRoot(container);
    const withoutAreas: VisitPatterns = {
      ...patterns,
      patterns_availability: "unavailable",
      patterns_unavailable_reason: "no_areas",
      area_transitions: [],
      sequences: [],
      shop_transitions: [],
    };
    try {
      await act(async () => root.render(<VisitPatternsPanel patterns={withoutAreas} shops={shops} />));
      const text = container.textContent ?? "";
      expect(text).toContain("No hay áreas.");
      expect(text).toContain("Visita 3");
      expect(text).not.toContain("0 transiciones");
      expect(text).not.toContain("Transiciones entre áreas");
    } finally {
      await act(async () => root.unmount());
    }
  });

  it("cero grupos disponibles se muestra como cero", async () => {
    const container = document.createElement("div");
    const root = createRoot(container);
    const none: VisitPatterns = { ...patterns, group_count: 0, groups: [] };
    try {
      await act(async () => root.render(<VisitPatternsPanel patterns={none} shops={shops} />));
      expect(container.textContent).toContain("0 grupos estimados");
      expect(container.textContent).not.toContain("no disponible");
    } finally {
      await act(async () => root.unmount());
    }
  });
});
