import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { LiveResultsPage } from "../src/pages/LiveResultsPage";

vi.mock("../src/components/CrossingChart", () => ({ CrossingChart: () => <p>Gráfico de cruces</p> }));
let root: Root, container: HTMLDivElement;
beforeEach(() => { vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true); container = document.createElement("div"); document.body.append(container); root = createRoot(container); });
afterEach(async () => { await act(async () => root.unmount()); container.remove(); vi.unstubAllGlobals(); });
function result(status = "completed") {
  return { job_id: "job-1", session_id: "session-1", source_kind: "webcam", status,
    capture_status: "ended", result_complete: status === "completed", coverage_complete: false,
    unknown_tail: status === "failed", elapsed_capture_seconds: 61, revision: 3,
    checkpoint_at: "2026-10-05T00:00:00Z", selected_shop_id: "shop-1",
    shops: [{ shop_id: "shop-1", shop_name: "Paso" }], summary: { shop_id: "shop-1",
      shop_name: "Paso", entry_count: 2, exit_count: 1, a_to_b_count: 2, b_to_a_count: 1,
      total_crossings: 3, label_mode: "directions", entry_direction: "a_to_b", partial: status !== "completed" },
    minutes: [], next_bucket_cursor: null, interruptions: [{ id: "gap-1", start_seconds: 60,
      end_seconds: status === "failed" ? null : 61, end_known: status !== "failed", reason: "capture_lost" }],
    observed_seconds: 60, missing_seconds: 1, unconfirmed_crossings: 1,
    sampling: { time_basis: "capture", sample_count: 20000, candidate_count: 90000, capacity: 20000 } };
}
function mockApi(status = "completed", overrides = {}, emptySamples = false) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => ({ ok: true, status: 200, text: async () => JSON.stringify(
    url.includes("position-samples") ? { job_id: "job-1", source_kind: "webcam", time_basis: "capture",
      availability: "available", sample_count: 20000, returned_count: 1, candidate_count: 90000,
      capacity: 20000, samples: emptySamples ? [] : [{ capture_timestamp_seconds: 5, foot: [0.5, 0.4] }] } :
    url.includes("live-events") ? { events: [], next_cursor: null } : { ...result(status), ...overrides }) })));
}

it("muestra entradas y salidas en resultados sin confundirlas con los lados A/B", async () => {
  mockApi("completed", { summary: { ...result().summary, label_mode: "access", entry_direction: "b_to_a",
    a_to_b_count: 1, b_to_a_count: 2 } });
  await act(async () => root.render(<LiveResultsPage jobId="job-1" apiBaseUrl="http://api.test" />));
  expect(container.textContent).toContain("Entradas: 2 · Salidas: 1");
  expect(container.textContent).not.toContain("A → B:");
});
it("muestra cruces, cobertura y muestra acotada sin reproducción ni chat", async () => {
  mockApi(); await act(async () => root.render(<LiveResultsPage jobId="job-1" apiBaseUrl="http://api.test" />));
  expect(container.textContent).toContain("Sin grabación");
  expect(container.textContent).toContain("Cobertura parcial");
  expect(container.textContent).toContain("No representa personas únicas");
  expect(container.querySelector('[aria-label="Total de cruces"]')?.textContent).toBe("3");
  expect(container.querySelector('svg[aria-label="Mapa de calor"]')).not.toBeNull();
  expect(container.querySelector("video")).toBeNull();
  expect(container.querySelector('textarea, input[placeholder*="pregunta"]')).toBeNull();
});
it("conserva la duración del último checkpoint y hace visible el final desconocido", async () => {
  mockApi("failed"); await act(async () => root.render(<LiveResultsPage jobId="job-1" apiBaseUrl="http://api.test" />));
  expect(container.textContent).toContain("Captura fallida");
  expect(container.textContent).not.toContain("Captura finalizada");
  expect(container.textContent).toContain("Resultados parciales");
  expect(container.textContent).toContain("Final desconocido");
  expect(container.textContent).toContain("61");
  expect(container.textContent).not.toContain("Análisis completo");
});

it("resume cobertura real y oculta la auditoría hasta expandirla", async () => {
  mockApi("completed", { elapsed_capture_seconds: 16, observed_seconds: 7, missing_seconds: 9 }, true);
  await act(async () => root.render(<LiveResultsPage jobId="job-1" apiBaseUrl="http://api.test" />));
  expect(container.querySelector('h1')?.textContent).toBe("Reporte de análisis · Webcam en vivo");
  expect(container.textContent).toContain("Cobertura parcial (7.0s / 16.0s observados)");
  expect(container.querySelector('[aria-label="Cobertura del análisis"]')?.textContent).toBe("43,8 %");
  expect(container.textContent).toContain("9,0 s sin analizar");
  expect(container.textContent).toContain("Sin estadía calculada");
  expect(container.querySelector('[aria-label="Estadía promedio interna"]')?.textContent).toBe("--");
  expect(container.textContent).toContain("Sin muestra de posiciones");
  const diagnosis = Array.from(container.querySelectorAll('details')).find(element => element.querySelector('summary')?.textContent?.includes("Diagnóstico técnico"));
  expect(diagnosis).toBeDefined();
  expect(diagnosis?.open).toBe(false);
  expect(diagnosis?.textContent).toContain("Cruces sin confirmar descartados");
  expect(diagnosis?.textContent).toContain("Asistente analítico no disponible");
});
it("no inventa un porcentaje sin duración y conserva la estadía observada", async () => {
  mockApi("completed", { elapsed_capture_seconds: 0, observed_seconds: 0, missing_seconds: 0,
    zone_dwell: { "shop-1": { interior_average_seconds: 12.5, interior_sample_count: 3,
      front_average_seconds: 7, front_sample_count: 2 } } });
  await act(async () => root.render(<LiveResultsPage jobId="job-1" apiBaseUrl="http://api.test" />));
  expect(container.querySelector('[aria-label="Cobertura del análisis"]')?.textContent).toBe("--");
  expect(container.textContent).toContain("3 visitas observadas");
  expect(container.querySelector('[aria-label="Estadía promedio interna"]')?.textContent).toBe("12,5 s");
  expect(container.querySelector('[aria-label="Estadía promedio externa"]')?.textContent).toBe("7 s");
});
it("distingue una captura cancelada y una estadía sin duración suficiente", async () => {
  mockApi("cancelled", { zone_dwell: { "shop-1": { interior_average_seconds: null, interior_sample_count: 0,
    front_average_seconds: null, front_sample_count: 0 } } });
  await act(async () => root.render(<LiveResultsPage jobId="job-1" apiBaseUrl="http://api.test" />));
  expect(container.textContent).toContain("Captura cancelada");
  expect(container.textContent).not.toContain("Captura finalizada");
  expect(container.textContent).toContain("Sin visitas con duración suficiente");
  expect(container.textContent).not.toContain("Sin tracks observados");
});
