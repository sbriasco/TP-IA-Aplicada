import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { JobPreviewPage } from "../src/pages/JobPreviewPage";

describe("JobPreviewPage", () => {
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

  it("informa cuando la API no está disponible", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));

    await act(async () => root.render(<JobPreviewPage jobId="job-1" />));

    expect(container.textContent).toContain("API no disponible");
    expect(container.querySelector("h1")?.textContent).toBe("Supervisión del trabajo");
    expect(container.querySelector("header")).not.toBeNull();
  });

  it("muestra un trabajo cancelado sin abrir WebSocket", async () => {
    const socket = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ id: "job-1", session_id: "session-1", status: "cancelled" }),
      }),
    );
    vi.stubGlobal("WebSocket", socket);

    await act(async () => root.render(<JobPreviewPage jobId="job-1" />));

    expect(container.textContent).toContain("Trabajo finalizado");
    expect(container.textContent).toContain("cancelled");
    expect(container.textContent).toContain("incompleto");
    expect(container.textContent).not.toContain("El análisis falló");
    expect(container.querySelector("button")).toBeNull();
    expect(socket).not.toHaveBeenCalled();
  });

  it("ofrece cancelar mientras el análisis procesa", async () => {
    const sockets: FakeSocket[] = [];

    class FakeSocket {
      listeners: Record<string, Array<(event: { data: string }) => void>> = {};

      constructor(_url: string) {
        sockets.push(this);
      }

      addEventListener(type: string, listener: (event: { data: string }) => void) {
        (this.listeners[type] ??= []).push(listener);
      }

      close() {}
    }

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ id: "job-1", session_id: "session-1", status: "processing" }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ id: "job-1", session_id: "session-1", status: "cancelled" }),
      });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("WebSocket", FakeSocket);

    await act(async () => root.render(<JobPreviewPage jobId="job-1" />));
    const button = container.querySelector("button");
    expect(button?.textContent).toBe("Cancelar análisis");

    await act(async () => {
      button?.click();
    });

    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8000/jobs/job-1/cancel", {
      method: "POST",
    });
    expect(container.textContent).toContain("incompleto");
    expect(container.textContent).not.toContain("El análisis falló");
    expect(container.querySelector("button")).toBeNull();
  });

  it("muestra un fallo distinto de una cancelación", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ id: "job-1", session_id: "session-1", status: "failed" }),
      }),
    );
    vi.stubGlobal("WebSocket", vi.fn());

    await act(async () => root.render(<JobPreviewPage jobId="job-1" />));

    expect(container.textContent).toContain("El análisis falló");
    expect(container.textContent).not.toContain("incompleto");
    expect(container.querySelector("button")).toBeNull();
  });

  it("muestra el instante del mensaje de video y no promete su velocidad", async () => {
    const sockets: FakeSocket[] = [];

    class FakeSocket {
      listeners: Record<string, Array<(event: { data: string }) => void>> = {};

      constructor(_url: string) {
        sockets.push(this);
      }

      addEventListener(type: string, listener: (event: { data: string }) => void) {
        (this.listeners[type] ??= []).push(listener);
      }

      close() {}
    }

    vi.stubGlobal("WebSocket", FakeSocket);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ id: "job-1", session_id: "session-1", status: "processing" }),
      }),
    );

    await act(async () => root.render(<JobPreviewPage jobId="job-1" />));
    const socket = sockets[0];
    expect(socket).toBeDefined();
    await act(async () => {
      for (const listener of socket?.listeners.message ?? []) {
        listener({
          data: JSON.stringify({
            type: "preview.update",
            schema_version: "2",
            frame_index: 10,
            video_timestamp_seconds: 0.4,
            progress_percent: 20,
            image_media_type: "image/jpeg",
            image_base64: "/9j/2Q==",
          }),
        });
      }
    });

    expect(container.textContent).toContain("0.4 s");
    expect(container.textContent).toContain("20 %");
    expect(container.textContent).toContain("no promete la velocidad del video");
    expect(container.querySelector("img")?.getAttribute("width")).toBeNull();
  });

  it("muestra directamente un trabajo terminal sin abrir WebSocket", async () => {
    const socket = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ id: "job-1", session_id: "session-1", status: "completed" }),
      }),
    );
    vi.stubGlobal("WebSocket", socket);

    await act(async () => root.render(<JobPreviewPage jobId="job-1" />));

    expect(container.textContent).toContain("Trabajo finalizado");
    expect(container.textContent).toContain("completed");
    expect(Array.from(container.querySelectorAll('a[href="/sessions/session-1/results"]')).some((link) => link.textContent === "Ver resultados")).toBe(true);
    expect(socket).not.toHaveBeenCalled();
  });
});
