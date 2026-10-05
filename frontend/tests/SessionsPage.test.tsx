import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SessionsPage } from "../src/pages/SessionsPage";
import { click } from "./dom";

const API = "http://api.test";
const camera = { id: "cam-1", name: "Cam 01", created_at: "2026-09-28T00:00:00Z" };

function response(status: number, body: unknown) {
  return { ok: status >= 200 && status < 300, status, text: async () => JSON.stringify(body) };
}

function routeFetch(sessions: unknown) {
  return vi.fn((url: string) => {
    if (url.startsWith(`${API}/processed-sessions`)) {
      return Promise.resolve(response(200, []));
    }
    return Promise.resolve(response(200, url.startsWith(`${API}/sessions`) ? sessions : [camera]));
  });
}

describe("SessionsPage", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    window.history.replaceState(null, "", "/");
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
    vi.unstubAllGlobals();
    window.history.replaceState(null, "", "/");
  });

  it("lista las sesiones con cámara y tipo, y navega al detalle", async () => {
    vi.stubGlobal(
      "fetch",
      routeFetch([
        { id: "s-1", name: "Mañana", source_kind: "video_file", camera, created_at: "2026-09-28T10:00:00Z" },
        { id: "s-2", name: "E2E", source_kind: "synthetic", camera, created_at: "2026-09-27T10:00:00Z" },
      ]),
    );

    await act(async () => root.render(<SessionsPage apiBaseUrl={API} />));

    expect(container.querySelector("h1")?.textContent).toBe("Tus análisis");

    const rows = Array.from(container.querySelectorAll("tbody tr")).map((row) =>
      Array.from(row.querySelectorAll("td"))
        .slice(0, 2)
        .map((cell) => cell.textContent),
    );
    expect(rows).toEqual([
      ["Mañana", "Cam 01"],
      ["E2E", "Cam 01"],
    ]);

    const link = container.querySelector('a[href="/sessions/s-1"]') as HTMLAnchorElement;
    await click(link);
    expect(window.location.pathname).toBe("/sessions/s-1");
  });

  it("informa cuando no hay sesiones", async () => {
    vi.stubGlobal("fetch", routeFetch([]));

    await act(async () => root.render(<SessionsPage apiBaseUrl={API} />));

    expect(container.textContent).toContain("Todavía no hay análisis.");
    expect(container.textContent).toContain("Nuevo análisis");
  });

  it("abre webcam activa y fallida en sus vistas y señala que no hay grabación", async () => {
    vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve(response(200,
      url.endsWith("/processed-sessions") ? [
        { session_id: "live-1", job_id: "job-1", status: "processing", source_kind: "webcam", result_complete: false },
        { session_id: "live-2", job_id: "job-2", status: "failed", source_kind: "webcam", result_complete: false },
      ] : [
        { id: "live-1", name: "Expo activa", source_kind: "webcam", camera, created_at: camera.created_at },
        { id: "live-2", name: "Expo parcial", source_kind: "webcam", camera, created_at: camera.created_at },
      ]))));
    await act(async () => root.render(<SessionsPage apiBaseUrl={API} />));
    expect(container.querySelector('a[href="/live/jobs/job-1"]')).not.toBeNull();
    expect(container.querySelector('a[href="/live/jobs/job-2/results"]')).not.toBeNull();
    expect(container.textContent).toContain("Sin grabación");
  });

  it("muestra el error de la API", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));

    await act(async () => root.render(<SessionsPage apiBaseUrl={API} />));

    expect(container.textContent).toContain("No se pudo conectar con la API");
  });

  it("muestra cada video una sola vez con su estado y abre la carga a pedido", async () => {
    vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve(response(200,
      url.endsWith("/processed-sessions") ? [{ session_id: "s-1", job_id: "j-1", status: "completed", result_complete: true }]
        : url.endsWith("/sessions") ? [{ id: "s-1", name: "Mañana", source_kind: "video_file", camera, created_at: "2026-09-28T10:00:00Z" }] : [camera],
    ))));
    await act(async () => root.render(<SessionsPage apiBaseUrl={API} />));
    expect(container.querySelectorAll("tbody tr")).toHaveLength(1);
    expect(container.textContent).toContain("Resultados listos");
    expect(container.querySelector('a[href="/sessions/s-1/results"]')?.textContent).toContain("Ver resultados");
    expect(container.querySelector('input[type="file"]')).toBeNull();
    const button = Array.from(container.querySelectorAll("button")).find((item) => item.textContent === "Nuevo análisis");
    await click(button as HTMLButtonElement);
    expect(container.querySelector('dialog input[type="file"]')).not.toBeNull();
  });

  it("solo elimina después de confirmar y conserva la fila ante un rechazo", async () => {
    const fetchMock = vi.fn((url: string, init?: RequestInit) => Promise.resolve(response(
      init?.method === "DELETE" ? 409 : 200,
      init?.method === "DELETE" ? { detail: { code: "session_busy", message: "Hay un análisis en curso." } }
        : url.endsWith("/sessions") ? [{ id: "s-1", name: "Mañana", source_kind: "video_file", camera, created_at: "2026-09-28T10:00:00Z" }]
          : [],
    )));
    vi.stubGlobal("fetch", fetchMock);
    await act(async () => root.render(<SessionsPage apiBaseUrl={API} />));
    await click(container.querySelector('button[aria-label="Eliminar Mañana"]') as HTMLButtonElement);
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "DELETE")).toBe(false);
    const confirm = Array.from(container.querySelectorAll("dialog button")).find((item) => item.textContent === "Eliminar del historial");
    await click(confirm as HTMLButtonElement);
    expect(container.textContent).toContain("Hay un análisis en curso.");
    expect(container.querySelectorAll("tbody tr")).toHaveLength(1);
  });

  it("muestra la lista mientras los estados siguen cargando", async () => {
    let finish: (value: unknown) => void = () => undefined;
    const pending = new Promise((resolve) => { finish = resolve; });
    vi.stubGlobal("fetch", vi.fn((url: string) => url.endsWith("/processed-sessions") ? pending : Promise.resolve(response(200,
      [{ id: "s-1", name: "Mañana", source_kind: "video_file", camera, created_at: "2026-09-28T10:00:00Z" }],
    ))));
    await act(async () => root.render(<SessionsPage apiBaseUrl={API} />));
    expect(container.querySelectorAll("tbody tr")).toHaveLength(1);
    expect(container.textContent).toContain("Cargando estado…");
    expect(container.querySelector("tbody")?.textContent).not.toContain("Sin analizar");
    await act(async () => finish(response(200, [])));
    expect(container.textContent).toContain("Sin analizar");
  });
});
