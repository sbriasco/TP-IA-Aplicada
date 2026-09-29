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
  return vi.fn((url: string) =>
    Promise.resolve(response(200, url.startsWith(`${API}/sessions`) ? sessions : [camera])),
  );
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

    const rows = Array.from(container.querySelectorAll("tbody tr")).map((row) =>
      Array.from(row.querySelectorAll("td"))
        .slice(0, 3)
        .map((cell) => cell.textContent),
    );
    expect(rows).toEqual([
      ["Mañana", "Cam 01", "Video"],
      ["E2E", "Cam 01", "Sintética"],
    ]);

    const link = container.querySelector('a[href="/sessions/s-1"]') as HTMLAnchorElement;
    await click(link);
    expect(window.location.pathname).toBe("/sessions/s-1");
  });

  it("informa cuando no hay sesiones", async () => {
    vi.stubGlobal("fetch", routeFetch([]));

    await act(async () => root.render(<SessionsPage apiBaseUrl={API} />));

    expect(container.textContent).toContain("Todavía no hay sesiones registradas.");
    expect(container.textContent).toContain("Registrar video");
  });

  it("muestra el error de la API", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));

    await act(async () => root.render(<SessionsPage apiBaseUrl={API} />));

    expect(container.textContent).toContain("No se pudo conectar con la API");
  });
});
