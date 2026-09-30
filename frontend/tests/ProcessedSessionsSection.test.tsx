import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ProcessedSessionsSection } from "../src/pages/ProcessedSessionsSection";

const API = "http://api.test";

function response(body: unknown) {
  return { ok: true, status: 200, text: async () => JSON.stringify(body) };
}

describe("ProcessedSessionsSection", () => {
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
    vi.unstubAllGlobals();
  });

  it("muestra la fila, el motivo de una fallida y el enlace a resultados", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          response([
            {
              session_id: "s-1",
              name: "Mañana",
              video_filename: "clip.avi",
              video_availability: "available",
              job_id: "j-1",
              status: "completed",
              finished_at: "2026-09-30T12:00:00Z",
              failure_code: null,
              failure_message: null,
              scene_version_id: "v-1",
              version_number: 2,
              result_complete: true,
            },
            {
              session_id: "s-2",
              name: "Rota",
              video_filename: "otra.avi",
              video_availability: "available",
              job_id: "j-2",
              status: "failed",
              finished_at: "2026-09-30T13:00:00Z",
              failure_code: "detector_failed",
              failure_message: "no se pudo analizar",
              scene_version_id: "v-1",
              version_number: 2,
              result_complete: false,
            },
          ]),
        ),
      ),
    );

    await act(async () => root.render(<ProcessedSessionsSection apiBaseUrl={API} />));

    const text = container.textContent ?? "";
    expect(text).toContain("Mañana");
    expect(text).toContain("clip.avi");
    expect(text).toContain("Completado");
    expect(text).toContain("2");
    expect(text).toContain("Fallido");
    expect(text).toContain("no se pudo analizar");
    expect(text).not.toContain("resultado final");
    const link = container.querySelector('a[href="/sessions/s-1/results"]');
    expect(link).not.toBeNull();
  });

  it("informa cuando no hay sesiones procesadas", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(response([]))));

    await act(async () => root.render(<ProcessedSessionsSection apiBaseUrl={API} />));

    expect(container.textContent).toContain("Todavía no hay sesiones procesadas.");
  });
});
