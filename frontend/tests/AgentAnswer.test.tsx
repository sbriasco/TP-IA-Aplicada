import { act } from "react";
import { createRoot } from "react-dom/client";
import { expect, it } from "vitest";

import { AgentAnswer } from "../src/components/AgentAnswer";
import type { ChatResponse } from "../src/api/chat";

it("presenta un pico sin métricas como no disponible", async () => {
  const container = document.createElement("div");
  const root = createRoot(container);
  const answer: ChatResponse = {
    status: "answered", message: "Este análisis no tiene métricas guardadas.",
    session_id: "session", shop_id: "shop", shop_name: "Local 1",
    scope: "whole_session", model_calls: 2,
    figures: [{
      code: "peak", label: "none", availability: "unavailable", value: null,
      unavailable_reason: "metrics_not_generated", start_seconds: null, track_count: null,
    }],
  };
  try {
    await act(async () => root.render(<AgentAnswer answer={answer} />));
    expect(container.querySelector("li")?.textContent).toBe("Horario pico: no disponible");
    expect(container.textContent).not.toContain("null");
    expect(container.textContent).not.toContain("0 s");
  } finally {
    await act(async () => root.unmount());
  }
});
