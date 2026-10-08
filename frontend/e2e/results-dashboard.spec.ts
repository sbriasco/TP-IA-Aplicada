import { expect, test } from "@playwright/test";

test("resultados: KPIs, área temporal, escena aplicada, tramo y agente", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  const camera = { id: "cam-1", name: "CamaraDePawn", created_at: "2026-10-06T00:00:00Z" };
  const version = { id: "v-1", camera_id: camera.id, version_number: 1, reference_session_id: "s-1", frame_width: 1280, frame_height: 720, shop_count: 1, created_at: camera.created_at, created_by_machine_id: null,
    shops: [{ shop_id: "zone-1", name: "Local 1", zones: { front: [[.1, .2], [.5, .2], [.5, .8], [.1, .8]] }, entry_line: { start: [.1, .8], end: [.5, .8], entry_direction: "a_to_b" } }] };
  await page.route("**/processed-sessions", route => route.fulfill({ json: [{ session_id: "s-1", name: "Dentro", video_filename: "Dentro de local.mp4", job_id: "job-1", status: "completed", result_complete: true, scene_version_id: "v-1", version_number: 1 }] }));
  await page.route("**/sessions/s-1", route => route.fulfill({ json: { id: "s-1", name: "Dentro", camera, source_kind: "video_file", created_at: camera.created_at,
    video: { original_filename: "Dentro de local.mp4", availability: "missing", duration_seconds: 98, width: 1280, height: 720 }, reference_frame: { width: 1280, height: 720, url: "/sessions/s-1/reference-frame" }, duplicate_session_ids: [] } }));
  await page.route("**/scene-versions/v-1", route => route.fulfill({ json: version }));
  await page.route("**/sessions/s-1/reference-frame", route => route.fulfill({ contentType: "image/svg+xml", body: '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720"><rect width="1280" height="720" fill="#343b40"/><path d="M0 720L450 200H830L1280 720" fill="#4f595d"/><rect x="480" y="150" width="320" height="370" fill="#627478"/></svg>' }));
  await page.route("**/sessions/s-1/shops/*/metrics", route => route.fulfill({ json: { session_id: "s-1", shop_id: "zone-1", metrics: [
    { code: "traffic_total", value: 89, availability: "available", label: "visit_estimate", unavailable_reason: null },
    { code: "entries", value: 5, availability: "available", label: "none", unavailable_reason: null },
    { code: "entry_rate", value: .0595, availability: "available", label: "none", unavailable_reason: null },
    { code: "dwell_mean_seconds", value: .79, availability: "available", label: "observable", unavailable_reason: null },
    { code: "store_pass", value: 84, availability: "available", label: "none", unavailable_reason: null },
    { code: "exits", value: 5, availability: "available", label: "none", unavailable_reason: null },
    { code: "dwell_median_seconds", value: .28, availability: "available", label: "observable", unavailable_reason: null },
    { code: "visible_occupancy", value: 0, availability: "available", label: "visible", unavailable_reason: null }], flow: [], peak: { start_seconds: 0, track_count: 67, bucket_index: 0 } } }));
  let fromSeconds = "";
  await page.route("**/sessions/s-1/events?*", route => {
    const url = new URL(route.request().url()); fromSeconds = url.searchParams.get("from_seconds") ?? "";
    const all = Array.from({ length: 12 }, (_, i) => [{ kind: "zone_enter", zone_role: "front", track_id: i, shop_id: "zone-1", video_timestamp_seconds: i * 6, duration_seconds: null }, { kind: "zone_exit", zone_role: "front", track_id: i, shop_id: "zone-1", video_timestamp_seconds: i * 6 + 22, duration_seconds: null }]).flat();
    return route.fulfill({ json: all.filter(event => event.video_timestamp_seconds >= Number(fromSeconds) && event.video_timestamp_seconds <= Number(url.searchParams.get("to_seconds"))) });
  });
  await page.route("**/jobs/job-1/position-samples", route => route.fulfill({ json: { job_id: "job-1", availability: "unavailable", samples: [] } }));
  let chatBody: unknown;
  await page.route("**/chat", async route => { chatBody = route.request().postDataJSON(); await route.fulfill({ json: { status: "answered", message: "Se registraron 5 entradas en esta zona.", session_id: "s-1", shop_id: "zone-1", shop_name: "Local 1", scope: "whole_session", figures: [], model_calls: 1 } }); });
  await page.emulateMedia({ colorScheme: "dark" });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/sessions/s-1/results");
  await expect(page.getByRole("heading", { name: "Dentro", exact: true })).toBeVisible();
  await expect(page.getByText("Zonas aplicadas: Versión 1", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "3 Resultados" })).toHaveAttribute("aria-current", "page");
  await expect(page.getByText("El archivo no está en este equipo.")).toHaveCount(0);
  await expect(page.getByText("No hay muestra de posiciones en este equipo.")).toHaveCount(0);
  const kpis = page.getByRole("region", { name: "Indicadores de la sesión" });
  await expect(kpis).toContainText("Tráfico estimado"); await expect(kpis).toContainText("89");
  await expect(kpis).toContainText("5,95 %"); await expect(kpis).toContainText("0,79 s");
  const frame = page.getByRole("img", { name: "Frame de referencia con zonas aplicadas" });
  await expect(frame.locator("polygon")).toHaveCount(1);
  expect((await frame.boundingBox())!.width).toBeGreaterThan(350);
  const scene = page.getByRole("region", { name: "Distribución en la escena" });
  expect((await frame.boundingBox())!.width / (await scene.boundingBox())!.width).toBeGreaterThan(.88);
  const chart = page.getByRole("img", { name: "Flujo temporal de tracks en el área externa" });
  await expect(chart.locator(".recharts-area-area")).toBeVisible();
  await chart.locator(".recharts-surface").focus();
  await chart.locator(".recharts-surface").press("ArrowRight");
  await expect(chart.locator(".recharts-tooltip-wrapper")).toContainText("Tracks en el área externa");
  await expect(chart).toContainText("0:25"); await expect(chart).toContainText("1:38");
  await kpis.getByText("Ver todos los indicadores", { exact: true }).click();
  const cards = kpis.getByRole("listitem");
  await expect(cards).toHaveCount(8);
  await expect(page.locator("header [data-context]")).toHaveCount(0);
  const heights = await cards.evaluateAll(elements => elements.map(element => element.getBoundingClientRect().height));
  expect(Math.max(...heights) - Math.min(...heights)).toBeLessThan(2);
  const facts = page.getByRole("button", { name: /Hechos del análisis/ });
  const sceneBox = (await scene.boundingBox())!;
  const factsBox = (await facts.boundingBox())!;
  expect(Math.abs(sceneBox.x - factsBox.x)).toBeLessThan(2);
  expect(factsBox.y - sceneBox.y - sceneBox.height).toBeLessThan(20);
  await expect(page.getByRole("region", { name: "Flujo temporal" }).getByRole("slider", { name: "Inicio del tramo" })).toBeVisible();
  await page.getByText("Alcance del tramo", { exact: true }).click();
  for (const viewport of [{ width: 1904, height: 914 }, { width: 1440, height: 900 }, { width: 1366, height: 768 }]) {
    await page.setViewportSize(viewport);
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollHeight <= innerHeight)).toBe(true);
    await expect(page.getByRole("button", { name: "Enviar", exact: true })).toBeInViewport();
    await expect(page.getByRole("region", { name: "Tramo temporal" })).toBeInViewport();
    await expect(page.getByText("El tramo recorta el gráfico y los hechos.", { exact: false })).toBeInViewport();
    await expect(frame).toBeInViewport();
    const flowBox = (await page.getByRole("region", { name: "Flujo temporal" }).boundingBox())!;
    const factsBox = (await facts.boundingBox())!;
    expect(Math.abs(flowBox.y + flowBox.height - factsBox.y - factsBox.height)).toBeLessThan(2);
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  await facts.click();
  const eventsDialog = page.getByRole("dialog", { name: "Hechos del análisis" });
  await expect(eventsDialog).toBeVisible();
  await expect(eventsDialog.getByRole("row")).toHaveCount(25);
  await expect(eventsDialog.getByRole("columnheader", { name: "Tiempo del video" })).toBeVisible();
  expect((await eventsDialog.getByRole("table").boundingBox())!.width).toBeGreaterThan(750);
  await page.screenshot({ path: "test-results/results-events-dialog.png" });
  await eventsDialog.getByRole("button", { name: "Cerrar", exact: true }).click();
  await expect(eventsDialog).toHaveCount(0);
  await page.screenshot({ path: "test-results/results-dashboard-dark.png", fullPage: true });
  const slider = page.getByRole("slider", { name: "Inicio del tramo" });
  await slider.press("ArrowRight"); await expect.poll(() => fromSeconds).toBe("0.1");
  await expect(kpis).toContainText("89");
  await page.getByRole("button", { name: "¿Cuántos ingresos hubo?" }).click();
  await page.getByRole("button", { name: "Enviar", exact: true }).click();
  await expect(page.getByRole("log")).toContainText("Se registraron 5 entradas");
  expect(chatBody).toEqual({ question: "¿Cuántos ingresos hubo?", session_id: "s-1", shop_id: "zone-1" });
  await page.getByRole("button", { name: "Activar modo claro" }).click();
  await page.screenshot({ path: "test-results/results-dashboard-light.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await expect(frame).toBeVisible();
  await page.screenshot({ path: "test-results/results-dashboard-mobile.png", fullPage: true });
  await page.route("**/jobs/job-1/position-samples", route => route.fulfill({ json: { job_id: "job-1", availability: "available", samples: [{ video_timestamp_seconds: 5, foot: [.2, .4] }] } }));
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.reload();
  const heatmap = page.getByRole("img", { name: "Mapa de calor" });
  await expect(heatmap).toBeVisible();
  expect(Math.abs((await heatmap.boundingBox())!.width - (await frame.boundingBox())!.width)).toBeLessThan(2);
  const caption = scene.locator("figcaption");
  await expect(caption).toBeInViewport();
  expect((await caption.boundingBox())!.y).toBeGreaterThanOrEqual((await frame.boundingBox())!.y + (await frame.boundingBox())!.height);
  expect(errors).toEqual([]);
});
