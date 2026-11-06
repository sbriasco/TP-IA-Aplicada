import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it } from "vitest";

import type { VisitPatterns, VisitSequence } from "../src/api/visitPatterns";
import { VisitPatternsPanel } from "../src/components/VisitPatternsPanel";

const zones = [
  { id: "z1", name: "Zona 1" },
];

function sequence(trackCount: number, roles: Array<"front" | "interior" | "window">): VisitSequence {
  return { areas: roles.map((role) => ({ shop_id: "z1", zone_role: role })), track_count: trackCount };
}

const patterns: VisitPatterns = {
  patterns_availability: "available",
  patterns_unavailable_reason: null,
  groups_availability: "available",
  group_count: 1,
  proximity_width_fraction: "0.16",
  direction_degrees: "90",
  minimum_seconds: "1",
  area_transitions: [
    {
      from_shop_id: "shop-norte",
      from_zone_role: "front",
      to_shop_id: "shop-sur",
      to_zone_role: "window",
      track_count: 2,
    },
  ],
  sequences: [],
  shop_transitions: [],
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
  it("muestra solo cuántos grupos se estimaron", async () => {
    const container = document.createElement("div");
    const root = createRoot(container);
    try {
      await act(async () => root.render(<VisitPatternsPanel patterns={patterns} />));
      const text = container.textContent ?? "";
      expect(text).toContain("1 grupo estimado");
      expect(text).not.toContain("Visita 3");
      expect(text).not.toContain("Transiciones entre áreas");
      expect(text).not.toContain("Umbrales");
      expect(text).not.toContain("precisión");
    } finally {
      await act(async () => root.unmount());
    }
  });

  it("cero grupos disponibles se muestra como cero", async () => {
    const container = document.createElement("div");
    const root = createRoot(container);
    const none: VisitPatterns = { ...patterns, group_count: 0, groups: [] };
    try {
      await act(async () => root.render(<VisitPatternsPanel patterns={none} />));
      expect(container.textContent).toContain("0 grupos estimados");
      expect(container.textContent).not.toContain("no disponible");
    } finally {
      await act(async () => root.unmount());
    }
  });

  it("muestra las cinco secuencias con más visitas y esconde el resto", async () => {
    const container = document.createElement("div");
    const root = createRoot(container);
    const ranked: VisitPatterns = {
      ...patterns,
      sequences: [
        sequence(5, ["interior"]),
        sequence(9, ["front"]),
        sequence(5, ["window"]),
        sequence(1, ["front", "interior"]),
        sequence(1, ["interior", "front"]),
        sequence(1, ["front", "interior", "front"]),
      ],
    };
    try {
      await act(async () => root.render(<VisitPatternsPanel patterns={ranked} zones={zones} />));
      const cards = [...container.querySelectorAll("li")].map((item) => item.textContent);
      expect(cards).toEqual([
        "Frente19",
        "Interior15",
        "Vidriera15",
        "Frente1 → Interior11",
        "Interior1 → Frente11",
      ]);
      expect(container.textContent).not.toContain("Frente1 ⇄ Interior1");
      const button = container.querySelector("button");
      expect(button?.textContent).toBe("Ver el resto de las secuencias");
      await act(async () => { button?.click(); });
      expect(container.textContent).toContain("Frente1 ⇄ Interior1");
      expect(button?.textContent).toBe("Ocultar el resto de las secuencias");
      expect(container.textContent).toContain("1 grupo estimado");
    } finally {
      await act(async () => root.unmount());
    }
  });

  it("no ofrece ampliar cuando hay cinco secuencias o menos", async () => {
    const container = document.createElement("div");
    const root = createRoot(container);
    const few: VisitPatterns = { ...patterns, sequences: [sequence(2, ["front"])] };
    try {
      await act(async () => root.render(<VisitPatternsPanel patterns={few} zones={zones} />));
      expect(container.textContent).toContain("Frente1");
      expect(container.querySelector("button")).toBeNull();
    } finally {
      await act(async () => root.unmount());
    }
  });

  it("informa cuando no hay secuencias", async () => {
    const container = document.createElement("div");
    const root = createRoot(container);
    try {
      await act(async () => root.render(<VisitPatternsPanel patterns={patterns} zones={zones} />));
      expect(container.textContent).toContain("No hay secuencias.");
    } finally {
      await act(async () => root.unmount());
    }
  });
});
