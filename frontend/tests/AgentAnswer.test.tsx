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

it("presenta la ayuda sin atribuirle el alcance de las métricas", async () => {
  const container = document.createElement("div");
  const root = createRoot(container);
  const message = "Hola. Puedo ayudarte a configurar zonas de análisis.\nTambién puedo explicar los límites de FlowSight.";
  const answer: ChatResponse = {
    status: "answered", message, session_id: "session", shop_id: null, shop_name: null,
    scope: null, model_calls: 1, figures: [],
  };
  try {
    await act(async () => root.render(<AgentAnswer answer={answer} />));
    expect(container.querySelector("p")?.textContent).toBe(message);
    expect(container.textContent).toContain("Ayuda de FlowSight");
    expect(container.textContent).not.toContain("toda la sesión");
    expect(container.querySelector("ul")).toBeNull();
  } finally {
    await act(async () => root.unmount());
  }
});

it("muestra etapas y conversiones del funnel con nombres y porcentajes", async () => {
  const container = document.createElement("div");
  const root = createRoot(container);
  const stageCodes = ["observed_pass", "exposure", "stop", "attention", "entries"];
  const rateCodes = ["observed_pass_to_exposure", "exposure_to_stop", "stop_to_attention", "attention_to_linked_entry"];
  const answer: ChatResponse = {
    status: "answered", message: "Estas son las etapas observadas y sus conversiones.",
    session_id: "session", shop_id: "shop", shop_name: "Zona central", scope: "whole_session", model_calls: 1,
    figures: [
      ...stageCodes.map((stage) => ({ code: `funnel_${stage}`, label: "none", availability: "available", value: 4, unavailable_reason: null, estimation: true })),
      ...rateCodes.map((rate) => ({ code: `funnel_${rate}_rate`, label: "none", availability: "available", value: 0.125, unavailable_reason: null, estimation: true })),
    ],
  };
  try {
    await act(async () => root.render(<AgentAnswer answer={answer} />));
    const rows = Array.from(container.querySelectorAll("li")).map((row) => row.textContent);
    expect(rows).toEqual([
      "Funnel (pasos observados): 4 · estimación",
      "Funnel (exposición): 4 · estimación",
      "Funnel (detención): 4 · estimación",
      "Funnel (atención estimada): 4 · estimación",
      "Funnel (entradas vinculadas): 4 · estimación",
      "Conversión de pasos a exposición: 12,5 % · estimación",
      "Conversión de exposición a detención: 12,5 % · estimación",
      "Conversión de detención a atención: 12,5 % · estimación",
      "Conversión de atención a entrada vinculada: 12,5 % · estimación",
    ]);
  } finally {
    await act(async () => root.unmount());
  }
});

it("mantiene formatos de webcam y tasas no disponibles sin convertirlas en cero", async () => {
  const container = document.createElement("div");
  const root = createRoot(container);
  const values: Record<string, number | null> = {
    total_crossings: 3,
    dwell_interior_mean_seconds: 12.5,
    dwell_front_mean_seconds: 7,
    coverage_percent: 43.75,
    elapsed_capture_seconds: 16,
    funnel_exposure_to_stop_rate: null,
  };
  const answer: ChatResponse = {
    status: "answered", message: "Este es el reporte de webcam.",
    session_id: "session", shop_id: "shop", shop_name: "Zona central", scope: "whole_session", model_calls: 1,
    figures: Object.entries(values).map(([code, value]) => ({
      code, label: "none", availability: value === null ? "unavailable" : "available", value,
      unavailable_reason: value === null ? "no_exposure" : null,
    })),
  };
  try {
    await act(async () => root.render(<AgentAnswer answer={answer} />));
    expect(Array.from(container.querySelectorAll("li")).map((row) => row.textContent)).toEqual([
      "Cruces totales: 3",
      "Permanencia interna: 12,5 s",
      "Permanencia externa: 7 s",
      "Cobertura: 43,75 %",
      "Duración de captura: 16 s",
      "Conversión de exposición a detención: no disponible",
    ]);
    await act(async () => root.render(<AgentAnswer answer={{
      ...answer, scope: "comparison", figures: [{
        code: "funnel_exposure_to_stop_rate__first", label: "none", availability: "available", value: 0.25, unavailable_reason: null,
      }],
    }} />));
    expect(container.querySelector("li")?.textContent).toContain("25 %");
  } finally {
    await act(async () => root.unmount());
  }
});
