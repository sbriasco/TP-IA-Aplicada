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
function mockApi(status = "completed") {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => ({ ok: true, status: 200, text: async () => JSON.stringify(
    url.includes("position-samples") ? { job_id: "job-1", source_kind: "webcam", time_basis: "capture",
      availability: "available", sample_count: 20000, returned_count: 1, candidate_count: 90000,
      capacity: 20000, samples: [{ capture_timestamp_seconds: 5, foot: [0.5, 0.4] }] } :
    url.includes("live-events") ? { events: [], next_cursor: null } : result(status)) })));
}
it("muestra cruces, cobertura y muestra acotada sin reproducción ni chat", async () => {
  mockApi(); await act(async () => root.render(<LiveResultsPage jobId="job-1" apiBaseUrl="http://api.test" />));
  expect(container.textContent).toContain("Sin grabación");
  expect(container.textContent).toContain("Cobertura incompleta");
  expect(container.textContent).toContain("No representa personas únicas");
  expect(container.querySelector('[aria-label="Total de cruces"]')?.textContent).toBe("3");
  expect(container.querySelector('svg[aria-label="Mapa de calor"]')).not.toBeNull();
  expect(container.querySelector("video")).toBeNull();
  expect(container.querySelector('textarea, input[placeholder*="pregunta"]')).toBeNull();
});
it("conserva la duración del último checkpoint y hace visible el final desconocido", async () => {
  mockApi("failed"); await act(async () => root.render(<LiveResultsPage jobId="job-1" apiBaseUrl="http://api.test" />));
  expect(container.textContent).toContain("Resultados parciales");
  expect(container.textContent).toContain("Final desconocido");
  expect(container.textContent).toContain("61");
  expect(container.textContent).not.toContain("Análisis completo");
});
