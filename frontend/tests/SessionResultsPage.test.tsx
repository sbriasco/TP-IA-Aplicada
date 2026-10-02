import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SessionResultsPage } from "../src/pages/SessionResultsPage";

const API = "http://api.test";

const metrics = {
  session_id: "s-1",
  shop_id: "shop-1",
  metrics: [
    { code: "traffic_total", availability: "available", value: 4, label: "visit_estimate", unavailable_reason: null },
    { code: "store_pass", availability: "available", value: 2, label: "none", unavailable_reason: null },
    { code: "entries", availability: "available", value: 1, label: "none", unavailable_reason: null },
    { code: "exits", availability: "available", value: 1, label: "none", unavailable_reason: null },
    { code: "entry_rate", availability: "unavailable", value: null, label: "none", unavailable_reason: "no_passes" },
    { code: "dwell_mean_seconds", availability: "available", value: 3, label: "observable", unavailable_reason: null },
    { code: "dwell_median_seconds", availability: "available", value: 3, label: "observable", unavailable_reason: null },
    { code: "visible_occupancy", availability: "available", value: 1, label: "visible", unavailable_reason: null },
  ],
  flow: [
    { bucket_index: 0, start_seconds: 0, track_count: 4 },
    { bucket_index: 1, start_seconds: 60, track_count: 1 },
  ],
  peak: { bucket_index: 0, start_seconds: 0, track_count: 4 },
};

function json(body: unknown) {
  return { ok: true, status: 200, text: async () => JSON.stringify(body) };
}

function completedRow(overrides: Record<string, unknown> = {}) {
  return {
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
    version_number: 1,
    result_complete: true,
    ...overrides,
  };
}

function detail(availability: string) {
  return {
    id: "s-1",
    name: "Mañana",
    source_kind: "video_file",
    camera_id: "cam",
    camera: { id: "cam", name: "Cam", created_at: "2026-09-30T00:00:00Z" },
    created_at: "2026-09-30T00:00:00Z",
    duplicate_session_ids: [],
    video: {
      relative_path: "clip.avi",
      original_filename: "clip.avi",
      size_bytes: 8,
      sha256: "a".repeat(64),
      origin_machine_id: "equipo",
      width: 320,
      height: 240,
      fps: 10,
      fps_is_estimated: false,
      frame_count: 10,
      declared_frame_count: 10,
      appears_incomplete: false,
      duration_seconds: 90,
      registered_at: "2026-09-30T00:00:00Z",
      availability,
    },
    reference_frame: {
      frame_index: 0,
      video_timestamp_seconds: 0,
      width: 320,
      height: 240,
      url: "/sessions/s-1/reference-frame",
    },
  };
}

describe("SessionResultsPage", () => {
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

  it("mantiene el frame cuando el video no está en este equipo", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.endsWith("/processed-sessions")) return Promise.resolve(json([completedRow({ video_availability: "missing" })]));
        if (url.endsWith("/sessions/s-1")) return Promise.resolve(json(detail("missing")));
        if (url.includes("/scene-versions/")) return Promise.resolve(json({ shops: [{ shop_id: "shop-1", name: "Local" }] }));
        if (url.includes("/metrics")) return Promise.resolve(json(metrics));
        if (url.includes("/events")) return Promise.resolve(json([]));
        if (url.includes("/position-samples")) {
          return Promise.resolve(json({ job_id: "j-1", availability: "unavailable", samples: [] }));
        }
        return Promise.resolve(json({}));
      }),
    );

    await act(async () => root.render(<SessionResultsPage sessionId="s-1" apiBaseUrl={API} />));

    expect(container.textContent).toContain("El archivo no está en este equipo.");
    expect(container.querySelector("img")?.getAttribute("src")).toBe(`${API}/sessions/s-1/reference-frame`);
    expect(container.textContent).toContain("Tráfico");
    expect(container.querySelector("h1")?.textContent).toBe("Mañana");
    expect(container.querySelector("header")?.textContent).toContain("Resultados");
    expect(Array.from(container.querySelectorAll("p")).some((node) => node.textContent === "s-1")).toBe(false);
  });

  it("no vuelve a pedir las métricas al mover el tramo y marca la tasa no disponible", async () => {
    const calls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        calls.push(url);
        if (url.endsWith("/processed-sessions")) return Promise.resolve(json([completedRow()]));
        if (url.endsWith("/sessions/s-1")) return Promise.resolve(json(detail("available")));
        if (url.includes("/scene-versions/")) return Promise.resolve(json({ shops: [{ shop_id: "shop-1", name: "Local" }] }));
        if (url.includes("/metrics")) return Promise.resolve(json(metrics));
        if (url.includes("/events")) return Promise.resolve(json([{ kind: "store_pass", zone_role: "front", track_id: 1, shop_id: "shop-1", video_timestamp_seconds: 10, duration_seconds: null }]));
        if (url.includes("/position-samples")) {
          return Promise.resolve(json({ job_id: "j-1", availability: "unavailable", samples: [] }));
        }
        return Promise.resolve(json({}));
      }),
    );

    await act(async () => root.render(<SessionResultsPage sessionId="s-1" apiBaseUrl={API} />));

    expect(container.textContent).toContain("estimación de visitas");
    expect(container.textContent).toContain("visible");
    expect(container.textContent).toContain("observable");
    expect(container.textContent).toContain("no disponible");
    expect(container.textContent).toContain("Horario pico: 0:00–1:00, 4");
    const metricsBefore = calls.filter((url) => url.includes("/metrics")).length;

    const from = container.querySelector('input[aria-label="Inicio del tramo"]') as HTMLInputElement;
    const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
    await act(async () => {
      setValue?.call(from, "50");
      from.dispatchEvent(new Event("input", { bubbles: true }));
      from.dispatchEvent(new Event("change", { bubbles: true }));
    });

    expect(calls.filter((url) => url.includes("/metrics")).length).toBe(metricsBefore);
    expect(calls.some((url) => url.includes("/events") && url.includes("from_seconds=50"))).toBe(true);
  });

  it("un resultado sintético sin escena informa indisponibilidad sin quedarse cargando", async () => {
    vi.stubGlobal("fetch", vi.fn((url: string) => {
      if (url.endsWith("/processed-sessions")) return Promise.resolve(json([completedRow({ scene_version_id: null, version_number: null })]));
      if (url.endsWith("/sessions/s-1")) return Promise.resolve(json({ ...detail("available"), source_kind: "synthetic", reference_frame: null, video: null }));
      if (url.includes("/position-samples")) return Promise.resolve(json({ job_id: "j-1", availability: "unavailable", samples: [] }));
      return Promise.resolve(json({}));
    }));
    await act(async () => root.render(<SessionResultsPage sessionId="s-1" apiBaseUrl={API} />));
    expect(container.textContent).not.toContain("Cargando indicadores");
    expect(container.textContent).toContain("Esta sesión no tiene indicadores comerciales");
  });

  it("en curso muestra solo las tres cifras parciales", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.endsWith("/processed-sessions")) {
          return Promise.resolve(json([completedRow({ status: "processing", result_complete: false, finished_at: null })]));
        }
        if (url.endsWith("/sessions/s-1")) return Promise.resolve(json(detail("available")));
        if (url.includes("/measures")) {
          return Promise.resolve(
            json([
              { shop_id: "shop-1", shop_name: "Local", code: "entries", value: 1, availability: "available", partial: true },
              { shop_id: "shop-1", shop_name: "Local", code: "exits", value: 0, availability: "available", partial: true },
              { shop_id: "shop-1", shop_name: "Local", code: "visible_occupancy", value: 1, availability: "available", partial: true },
            ]),
          );
        }
        return Promise.resolve(json({}));
      }),
    );

    await act(async () => root.render(<SessionResultsPage sessionId="s-1" apiBaseUrl={API} />));

    const text = container.textContent ?? "";
    expect(text).toContain("Entradas");
    expect(text).toContain("Salidas");
    expect(text).toContain("Ocupación visible");
    expect(text).toContain("parcial");
    expect(text).not.toContain("Tráfico");
    expect(text).not.toContain("Tasa de ingreso");
  });

  it("un análisis fallido muestra el motivo y ningún indicador", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.endsWith("/processed-sessions")) {
          return Promise.resolve(
            json([
              completedRow({
                status: "failed",
                result_complete: false,
                failure_message: "no se pudo analizar",
              }),
            ]),
          );
        }
        if (url.endsWith("/sessions/s-1")) return Promise.resolve(json(detail("available")));
        return Promise.resolve(json({}));
      }),
    );

    await act(async () => root.render(<SessionResultsPage sessionId="s-1" apiBaseUrl={API} />));

    expect(container.textContent).toContain("no se pudo analizar");
    expect(container.textContent).not.toContain("Tráfico");
  });

  it("el panel viaja con la sesión y el local, y se vacía al cambiar de sesión", async () => {
    const calls: { url: string; body?: string }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        calls.push({ url, body: typeof init?.body === "string" ? init.body : undefined });
        if (url.endsWith("/chat")) {
          const payload = JSON.parse(String(init?.body)) as { session_id: string };
          return Promise.resolve(
            json({
              status: "answered",
              message: `Respuesta de ${payload.session_id}`,
              session_id: payload.session_id,
              shop_id: "shop-1",
              shop_name: "Local",
              scope: "whole_session",
              figures: [],
              model_calls: 1,
            }),
          );
        }
        if (url.endsWith("/processed-sessions")) {
          return Promise.resolve(
            json([completedRow(), completedRow({ session_id: "s-2", name: "Tarde", job_id: "j-2" })]),
          );
        }
        if (url.endsWith("/sessions/s-1") || url.endsWith("/sessions/s-2")) {
          const sessionId = url.endsWith("/sessions/s-2") ? "s-2" : "s-1";
          return Promise.resolve(json({ ...detail("available"), id: sessionId }));
        }
        if (url.includes("/scene-versions/")) return Promise.resolve(json({ shops: [{ shop_id: "shop-1", name: "Local" }] }));
        if (url.includes("/metrics")) return Promise.resolve(json(metrics));
        if (url.includes("/events")) return Promise.resolve(json([]));
        if (url.includes("/position-samples")) {
          return Promise.resolve(json({ job_id: "j-1", availability: "unavailable", samples: [] }));
        }
        return Promise.resolve(json({}));
      }),
    );

    await act(async () => root.render(<SessionResultsPage sessionId="s-1" apiBaseUrl={API} />));

    const field = container.querySelector('input[name="question"]') as HTMLInputElement;
    const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
    await act(async () => {
      setValue?.call(field, "¿cuál es el tráfico?");
      field.dispatchEvent(new Event("input", { bubbles: true }));
      container.querySelector("form")?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    });

    const chat = calls.find((call) => call.url.endsWith("/chat"));
    expect(JSON.parse(chat?.body ?? "{}")).toEqual({
      question: "¿cuál es el tráfico?",
      session_id: "s-1",
      shop_id: "shop-1",
    });
    expect(container.textContent).toContain("Respuesta de s-1");

    await act(async () => root.render(<SessionResultsPage sessionId="s-2" apiBaseUrl={API} />));
    expect(container.textContent).not.toContain("Respuesta de s-1");
  });

  it("un error del chat no oculta los indicadores", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.endsWith("/chat")) {
          return Promise.resolve(
            json({
              status: "error",
              message: "La pregunta tardó demasiado. Podés volver a intentar.",
              session_id: "s-1",
              shop_id: "shop-1",
              shop_name: null,
              scope: null,
              figures: [],
              model_calls: 0,
            }),
          );
        }
        if (url.endsWith("/processed-sessions")) return Promise.resolve(json([completedRow()]));
        if (url.endsWith("/sessions/s-1")) return Promise.resolve(json(detail("available")));
        if (url.includes("/scene-versions/")) return Promise.resolve(json({ shops: [{ shop_id: "shop-1", name: "Local" }] }));
        if (url.includes("/metrics")) return Promise.resolve(json(metrics));
        if (url.includes("/events")) return Promise.resolve(json([]));
        if (url.includes("/position-samples")) {
          return Promise.resolve(json({ job_id: "j-1", availability: "unavailable", samples: [] }));
        }
        return Promise.resolve(json({}));
      }),
    );

    await act(async () => root.render(<SessionResultsPage sessionId="s-1" apiBaseUrl={API} />));
    const field = container.querySelector('input[name="question"]') as HTMLInputElement;
    const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
    await act(async () => {
      setValue?.call(field, "tráfico");
      field.dispatchEvent(new Event("input", { bubbles: true }));
      container.querySelector("form")?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    });

    expect(container.textContent).toContain("La pregunta tardó demasiado. Podés volver a intentar.");
    expect(container.textContent).toContain("Tráfico");
  });
});
