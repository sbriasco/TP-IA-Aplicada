import { expect, test } from "@playwright/test";
import type { LiveResults } from "../src/types/live";

const report: LiveResults = {
  job_id: "report-1", session_id: "session-1", source_kind: "webcam", status: "completed",
  capture_status: "ended", result_complete: true, coverage_complete: false, unknown_tail: false,
  elapsed_capture_seconds: 16, observed_seconds: 7, missing_seconds: 9, revision: 3,
  capture_started_at: "2026-10-06T20:21:00Z", checkpoint_at: "2026-10-06T20:21:16Z",
  selected_shop_id: "line-1", shops: [{ shop_id: "line-1", shop_name: "Prueba" }, { shop_id: "line-2", shop_name: "Acceso" }],
  summary: { shop_id: "line-1", shop_name: "Prueba", entry_count: 0, exit_count: 0, a_to_b_count: 0,
    b_to_a_count: 0, total_crossings: 0, label_mode: "directions", partial: false, entry_direction: "a_to_b" },
  minutes: [{ shop_id: "line-1", bucket_index: 0, start_seconds: 0, end_seconds: 16, entries: 0, exits: 0,
    observed_seconds: 7, missing_seconds: 9, pending_count: 0, is_open: false, coverage_incomplete: true, unknown_tail: false, revision: 3 }],
  next_bucket_cursor: null, interruptions: [{ id: "gap-1", start_seconds: 0, end_seconds: 9, end_known: true, reason: "analysis_gap" }],
  unconfirmed_crossings: 0, zone_dwell: {}, sampling: { time_basis: "capture", sample_count: 0, candidate_count: 0, capacity: 20000 },
};

test("reporte webcam: paleta uniforme, KPIs, diagnóstico y diseño responsive", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.route("**/jobs/report-1/live-results?*", route => {
    const selected = new URL(route.request().url()).searchParams.get("shop_id");
    return route.fulfill({ json: selected === "line-2" ? { ...report, selected_shop_id: selected,
      summary: { ...report.summary, shop_id: selected, shop_name: "Acceso", label_mode: "access" },
    } : report });
  });
  await page.route("**/jobs/report-1/position-samples", route => route.fulfill({ json: {
    job_id: "report-1", source_kind: "webcam", time_basis: "capture", availability: "unavailable",
    sample_count: 0, returned_count: 0, candidate_count: 0, capacity: 20000, samples: [],
  } }));
  await page.route("**/jobs/report-1/live-events*", route => route.fulfill({ json: { events: [], next_cursor: null } }));
  await page.emulateMedia({ colorScheme: "light" });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/live/jobs/report-1/results");
  await expect(page.getByRole("heading", { name: "Reporte de análisis · Webcam en vivo" })).toBeVisible();
  await expect(page.getByText("06/10/2026, 17:21", { exact: true })).toBeVisible();
  await expect(page.getByText("Captura finalizada", { exact: true })).toBeVisible();
  await expect(page.getByText("Cobertura parcial (7.0s / 16.0s observados)")).toHaveAttribute("title", /interrupciones/);
  await expect(page.getByLabel("Cobertura del análisis", { exact: true })).toHaveText("43,8 %");
  await expect(page.getByText("9,0 s sin analizar", { exact: true })).toBeVisible();
  await expect(page.getByText("Sin estadía calculada", { exact: true })).toHaveCount(2);
  await expect(page.getByLabel("Estadía promedio interna", { exact: true })).toHaveText("--");
  await expect(page.getByRole("heading", { name: "Sin muestra de posiciones", exact: true })).toBeVisible();
  await expect(page.locator("body")).toHaveCSS("background-color", "rgb(247, 248, 249)");
  const flow = page.getByRole("region", { name: "Flujo de cruces temporales", exact: true });
  const map = page.getByRole("region", { name: "Mapa de posiciones", exact: true });
  await expect(flow).toHaveCSS("background-color", "rgb(255, 255, 255)");
  await expect(map).toHaveCSS("background-color", "rgb(255, 255, 255)");
  await expect(page.locator(".recharts-wrapper")).toHaveCSS("height", "220px");
  const flowBounds = await flow.boundingBox(), mapBounds = await map.boundingBox();
  expect(Math.abs(flowBounds!.y - mapBounds!.y)).toBeLessThan(2);
  expect(Math.abs(flowBounds!.height - mapBounds!.height)).toBeLessThan(2);
  await expect(page.getByText("analysis_gap", { exact: false })).toBeHidden();
  await expect(page.getByText(/Asistente analítico no disponible/)).toBeHidden();
  await page.screenshot({ path: "test-results/webcam-report-light.png", fullPage: true });
  await page.getByRole("button", { name: "Activar modo oscuro", exact: true }).click();
  await expect(page.locator("body")).toHaveCSS("background-color", "rgb(20, 24, 27)");
  await expect(flow).toHaveCSS("background-color", "rgb(29, 30, 34)");
  await expect(map).toHaveCSS("background-color", "rgb(29, 30, 34)");
  await page.screenshot({ path: "test-results/webcam-report-dark.png", fullPage: true });
  await page.getByText("Diagnóstico técnico de la captura (Interrupciones y descarte)", { exact: true }).click();
  await expect(page.getByText("analysis_gap", { exact: false })).toBeVisible();
  await expect(page.getByText("0 cruces individuales", { exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Cobertura por minuto" }).getByRole("rowheader", { name: "17:21" })).toBeVisible();
  await page.getByRole("combobox", { name: "Zona" }).selectOption("line-2");
  await expect(page.getByText("Entradas: 0 · Salidas: 0", { exact: true })).toBeVisible();
  await expect(page.locator("details")).not.toHaveAttribute("open");
  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: "test-results/webcam-report-mobile.png", fullPage: true });
  await page.route("**/sessions", route => route.fulfill({ json: [] }));
  await page.route("**/processed-sessions", route => route.fulfill({ json: [] }));
  await page.getByRole("link", { name: "Volver a mis análisis", exact: true }).click();
  await expect(page.locator("body")).toHaveCSS("background-color", "rgb(20, 24, 27)");
  await page.getByRole("button", { name: "Activar modo claro", exact: true }).click();
  await expect(page.locator("body")).toHaveCSS("background-color", "rgb(247, 248, 249)");
  expect(errors).toEqual([]);
});

test("reporte webcam: muestras, dirección invertida y paginación conservadas", async ({ page }) => {
  const full: LiveResults = { ...report, coverage_complete: true, elapsed_capture_seconds: 125, observed_seconds: 125, missing_seconds: 0,
    interruptions: [], next_bucket_cursor: 1, summary: { ...report.summary!, total_crossings: 3,
      entry_count: 1, exit_count: 2, a_to_b_count: 2, b_to_a_count: 1, entry_direction: "b_to_a" },
    zone_dwell: { "line-1": { interior_average_seconds: 12.5, front_average_seconds: 7, interior_sample_count: 3, front_sample_count: 2 } },
    minutes: [{ ...report.minutes[0], end_seconds: 60, observed_seconds: 60, missing_seconds: 0, entries: 1, exits: 2, coverage_incomplete: false }],
  };
  await page.route("**/jobs/report-1/live-results?*", route => route.fulfill({ json:
    new URL(route.request().url()).searchParams.has("bucket_cursor") ? { ...full, next_bucket_cursor: null,
      minutes: [{ ...full.minutes[0], bucket_index: 1, start_seconds: 60, end_seconds: 120, observed_seconds: 0, missing_seconds: 60, coverage_incomplete: true }],
    } : full,
  }));
  await page.route("**/jobs/report-1/position-samples", route => route.fulfill({ json: {
    job_id: "report-1", source_kind: "webcam", time_basis: "capture", availability: "available",
    sample_count: 1, returned_count: 1, candidate_count: 1, capacity: 20000,
    samples: [{ capture_timestamp_seconds: 5, foot: [0.5, 0.4] }],
  } }));
  await page.route("**/sessions/session-1/reference-frame", route => route.fulfill({ contentType: "image/svg+xml", body:
    '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180"><rect width="320" height="180" fill="#1e293b"/></svg>',
  }));
  await page.route("**/jobs/report-1/live-events*", route => route.fulfill({ json:
    new URL(route.request().url()).searchParams.has("cursor") ? { events: [{ id: "e2", track_id: 2, capture_timestamp_seconds: 10, confirmed_at_capture_seconds: 11, direction: "exit" }], next_cursor: null } :
      { events: [{ id: "e1", track_id: 1, capture_timestamp_seconds: 5, confirmed_at_capture_seconds: 6, direction: "entry" }], next_cursor: "next" },
  }));
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/live/jobs/report-1/results");
  await expect(page.getByLabel("Estadía promedio interna", { exact: true })).toHaveText("12,5 s");
  await expect(page.getByRole("img", { name: "Mapa de calor", exact: true })).toBeVisible();
  await expect(page.getByText(/Cobertura parcial/)).toHaveCount(0);
  await page.getByRole("button", { name: "Cargar más minutos" }).click();
  await page.getByText("Diagnóstico técnico de la captura (Interrupciones y descarte)", { exact: true }).click();
  const coverage = page.getByRole("region", { name: "Cobertura por minuto" });
  await expect(coverage.getByRole("row", { name: "17:21 2 1 Minuto cerrado" })).toBeVisible();
  await expect(coverage.getByRole("row", { name: "17:22 Sin datos Sin datos Cobertura incompleta" })).toBeVisible();
  const events = page.getByRole("region", { name: "Registro de cruces" });
  await expect(events.getByRole("row", { name: "5.00 6.00 B → A" })).toBeVisible();
  await page.getByRole("button", { name: "Cargar más cruces" }).click();
  await expect(events.getByRole("row", { name: "10.00 11.00 A → B" })).toBeVisible();
  await expect(events.getByRole("row")).toHaveCount(3);
});
