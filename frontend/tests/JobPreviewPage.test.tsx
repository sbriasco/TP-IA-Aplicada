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
    expect(socket).not.toHaveBeenCalled();
  });
});
