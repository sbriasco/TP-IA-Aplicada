import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createComparison, type ComparisonResponse } from "../src/api/comparisons";
import { ComparisonPage } from "../src/pages/ComparisonPage";

const sessions = [
  {
    session_id: "11111111-1111-1111-1111-111111111111",
    name: "Sesión A",
    video_filename: "a.mp4",
    video_availability: "available" as const,
    job_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    status: "completed" as const,
    finished_at: "2026-09-01T12:00:00Z",
    failure_code: null,
    failure_message: null,
    scene_version_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    version_number: 1,
    result_complete: true,
    source_kind: "synthetic" as const,
  },
  {
    session_id: "22222222-2222-2222-2222-222222222222",
    name: "Sesión B",
    video_filename: "b.mp4",
    video_availability: "available" as const,
    job_id: "cccccccc-cccc-cccc-cccc-cccccccccccc",
    status: "completed" as const,
    finished_at: "2026-09-02T12:00:00Z",
    failure_code: null,
    failure_message: null,
    scene_version_id: "dddddddd-dddd-dddd-dddd-dddddddddddd",
    version_number: 2,
    result_complete: true,
    source_kind: "video_file" as const,
  },
  {
    session_id: "33333333-3333-3333-3333-333333333333",
    name: "Cámara",
    video_filename: null,
    video_availability: null,
    job_id: "ffffffff-ffff-ffff-ffff-ffffffffffff",
    status: "completed" as const,
    finished_at: "2026-09-03T12:00:00Z",
    failure_code: null,
    failure_message: null,
    scene_version_id: "99999999-9999-9999-9999-999999999999",
    version_number: 1,
    result_complete: true,
    source_kind: "webcam" as const,
  },
];

const comparison: ComparisonResponse = {
  axis: "session",
  zone_name: "Local",
  columns: [
    {
      key: "session:1",
      label: "Sesión A",
      session_ids: [sessions[0].session_id],
      camera_label: "Cam 1",
      resolved_shop_id: null,
    },
    {
      key: "session:2",
      label: "Sesión B",
      session_ids: [sessions[1].session_id],
      camera_label: "Cam 1",
      resolved_shop_id: null,
    },
  ],
  figures: [
    {
      family: "shop_metrics",
      code: "traffic_total",
      label: "Tráfico (estimación de visitas)",
      cells: [
        { availability: "available", value: 20, unavailable_reason: null },
        { availability: "unavailable", value: null, unavailable_reason: "zone_not_in_scene" },
      ],
      relation: "unavailable",
      delta: null,
    },
  ],
  insights: [
    {
      code: "no_highlights",
      message: "No hay diferencias destacables o faltan datos.",
      figure_code: null,
      estimation: false,
    },
  ],
};

vi.mock("../src/api/processedSessions", () => ({
  listProcessedSessions: vi.fn(async () => sessions),
}));

vi.mock("../src/api/metrics", () => ({
  getSceneShops: vi.fn(async () => [
    {
      shop_id: "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
      name: "Zona 1",
      zones: {},
      entry_line: {
        start: [0, 0],
        end: [1, 0],
        entry_direction: "a_to_b" as const,
      },
    },
  ]),
}));

vi.mock("../src/api/comparisons", async () => {
  const actual = await vi.importActual<typeof import("../src/api/comparisons")>(
    "../src/api/comparisons",
  );
  return {
    ...actual,
    createComparison: vi.fn(async () => comparison),
  };
});

describe("ComparisonPage", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
  });

  it("pide al menos dos sesiones y muestra no disponible e insights", async () => {
    await act(async () => {
      root.render(<ComparisonPage apiBaseUrl="http://test" />);
    });
    await act(async () => {
      await Promise.resolve();
    });
    await act(async () => {
      await Promise.resolve();
    });
    const zoneSelect = container.querySelector("select");
    expect(zoneSelect).toBeTruthy();
    expect(Array.from(zoneSelect?.options ?? []).map((option) => option.textContent)).toContain(
      "Zona 1",
    );
    expect(container.querySelector('input[type="text"]')).toBeNull();
    expect(container.textContent).toContain("Seleccioná al menos dos sesiones elegibles");
    expect(container.textContent).not.toContain("Día (cierre UTC");
    expect(container.textContent).not.toContain("Horario (tiempo de video)");
    expect(container.textContent).not.toContain("Zona (misma cámara)");
    const boxes = container.querySelectorAll('input[type="checkbox"]');
    expect(boxes.length).toBe(3);
    expect(container.textContent).toContain("Cámara · en vivo");
    await act(async () => {
      (boxes[0] as HTMLInputElement).click();
      (boxes[1] as HTMLInputElement).click();
      (boxes[2] as HTMLInputElement).click();
    });
    expect(container.textContent).toContain("Compará sesiones en vivo entre sí, o archivos entre sí.");
    const blocked = Array.from(container.querySelectorAll("button")).find((node) =>
      node.textContent?.includes("Comparar"),
    );
    expect(blocked?.hasAttribute("disabled")).toBe(true);
    await act(async () => {
      (boxes[2] as HTMLInputElement).click();
    });
    const button = Array.from(container.querySelectorAll("button")).find(
      (node) => node.textContent?.includes("Comparar"),
    );
    expect(button).toBeTruthy();
    await act(async () => {
      button?.click();
      await Promise.resolve();
    });
    await act(async () => {
      await Promise.resolve();
    });
    expect(createComparison).toHaveBeenCalledWith(
      "http://test",
      expect.objectContaining({ zone_name: "Zona 1", axis: "session" }),
    );
    expect(container.textContent).toContain("No disponible");
    expect(container.textContent).toContain("No hay diferencias destacables o faltan datos.");
    expect(container.textContent).toContain("Tráfico");
  });
});
