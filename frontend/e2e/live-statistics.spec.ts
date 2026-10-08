import { expect, test } from "@playwright/test";
import type { SceneVersion, SceneVersionCreate } from "../src/types/scene";

for (const labelMode of ["access", "directions"] as const) {
test(`pausa webcam: recarga, teclado, retomar y layout (${labelMode})`, async ({ page }) => {
  await page.emulateMedia({ colorScheme: labelMode === "access" ? "dark" : "light" });
  let captureStatus = "connected", revision = 3, segment = 0;
  const selected = { ...summary, label_mode: labelMode };
  let send: (value: object) => void = () => undefined;
  const status = () => ({ type: "live.status", schema_version: "3", source_kind: "webcam",
    job_id: "job-1", session_id: "session-1", status: "processing", revision,
    capture_status: captureStatus, capture_timestamp_seconds: 125, coverage_complete: false, unknown_tail: false });
  const frame = () => ({ type: "live.update", schema_version: "3", source_kind: "webcam",
    job_id: "job-1", session_id: "session-1", revision, capture_sequence: 100 + segment,
    segment_index: segment, capture_status: "connected", capture_timestamp_seconds: 125 + segment * 60,
    captured_monotonic_ms: 1000, published_monotonic_ms: 1100, image_media_type: "image/jpeg",
    image_base64: image, partial: true, capture_fps: 30, analysis_fps: 10, capture_to_publish_ms: 100,
    shops: [selected], minutes: result.minutes, coverage_complete: false,
    checkpoint_revision: revision, checkpoint_at: result.checkpoint_at,
  });
  await page.route("**/sessions/session-1", route => route.fulfill({ json: { id: "session-1", name: "Entrada", camera } }));
  await page.route("**/jobs/job-1/live-results?*", route => route.fulfill({ json: { ...result, capture_status: captureStatus, revision, summary: selected } }));
  await page.routeWebSocket("**/ws/jobs/job-1/preview", socket => {
    send = value => socket.send(JSON.stringify(value));
    socket.onMessage(() => send(captureStatus === "connected" ? frame() : status()));
  });
  await page.route("**/jobs/job-1/live/pause", async route => {
    captureStatus = "paused"; revision++;
    await route.fulfill({ status: 202, json: { job_id: "job-1", pause_requested: true } });
    send(status());
  });
  await page.route("**/jobs/job-1/live/continue", async route => {
    captureStatus = "awaiting_confirmation"; revision++;
    await route.fulfill({ status: 202, json: { job_id: "job-1", resume_requested: true } });
    send({ type: "live.reconnect-check", schema_version: "3", source_kind: "webcam",
      job_id: "job-1", session_id: "session-1", revision, segment_index: 1,
      capture_status: "awaiting_confirmation", device_index: 0, width: 320, height: 180,
      backend: "fake", image_media_type: "image/jpeg", image_base64: image,
      check_token: "new-probe", expires_in_seconds: 60 });
  });
  await page.route("**/jobs/job-1/live/confirm-resume", async route => {
    expect(route.request().postDataJSON()).toEqual({ check_token: "new-probe", frame_confirmed: true });
    captureStatus = "connected"; revision++; segment = 1;
    await route.fulfill({ status: 202, json: { job_id: "job-1", resume_requested: true } });
    send(frame());
  });
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto("/live/jobs/job-1");
  await expect(page.getByRole("img", { name: "Cámara en vivo", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Pausar análisis", exact: true }).focus();
  await page.keyboard.press("Space");
  await expect(page.getByRole("button", { name: "Retomar análisis", exact: true })).toBeEnabled();
  await page.reload();
  await expect(page.getByRole("button", { name: "Retomar análisis", exact: true })).toBeEnabled();
  await expect(page.getByLabel("Total de cruces", { exact: true })).toHaveText("9");
  for (const viewport of [{ width: 1366, height: 768 }, { width: 1920, height: 900 }]) {
    await page.setViewportSize(viewport);
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollHeight <= innerHeight)).toBe(true);
    await expect(page.getByText(/Última sincronización:/)).toBeInViewport();
    const panel = page.getByRole("complementary", { name: "Estadísticas en vivo" });
    await expect.poll(() => panel.evaluate(element => element.scrollHeight <= element.clientHeight)).toBe(true);
  }
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.screenshot({ path: `test-results/live-paused-${labelMode}.png` });
  await page.getByRole("button", { name: "Retomar análisis", exact: true }).click();
  await expect(page.getByRole("img", { name: "Encuadre para reanudar" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Reanudar análisis", exact: true })).toBeDisabled();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollHeight <= innerHeight)).toBe(true);
  await expect(page.getByText(/Última sincronización:/)).toBeInViewport();
  await expect.poll(() => page.getByRole("complementary", { name: "Estadísticas en vivo" }).evaluate(element => element.scrollHeight <= element.clientHeight)).toBe(true);
  await page.screenshot({ path: `test-results/live-resume-${labelMode}.png` });
  await page.getByLabel("Confirmo que el encuadre coincide con la configuración").check();
  await page.getByRole("button", { name: "Reanudar análisis", exact: true }).click();
  await expect(page.getByRole("img", { name: "Cámara en vivo", exact: true })).toBeVisible();
  await expect(page.getByLabel("Total de cruces", { exact: true })).toHaveText("9");
  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
}

// UI-only fixtures: no worker, camera or database writes are required.
const camera = { id: "camera-1", name: "Cámara de prueba", created_at: "2026-10-05T20:21:00Z" };

test("preparación webcam: dispositivos reconocidos y formulario sin controles superpuestos", async ({ page }) => {
  await page.route("**/cameras", (route) => route.fulfill({ json: [camera] }));
  await page.route("**/live/devices", (route) => route.fulfill({ json: {
    machine_id: "local-device", worker_available: true, candidates: [
      { device_index: 0, label: "Integrated Camera", verified: false },
      { device_index: 1, label: "Logitech USB", verified: false },
    ],
  } }));
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/live");
  await expect(page.getByRole("combobox", { name: "Webcam", exact: true }).getByRole("option", { name: "Logitech USB" })).toHaveCount(1);
  await page.getByLabel("Nombre de la sesión", { exact: true }).fill("Entrada · turno mañana");
  await page.getByLabel("Ubicación asignada", { exact: true }).selectOption(camera.id);
  await page.getByLabel("Webcam", { exact: true }).selectOption("1");
  await expect(page.getByRole("button", { name: "Preparar webcam y continuar", exact: true })).toBeEnabled();
  await expect(page.getByText(/Configurá el equipo|\.env/)).toHaveCount(0);
  const nameBounds = await page.getByLabel("Nombre de la sesión", { exact: true }).boundingBox();
  const labelBounds = await page.locator("label").filter({ hasText: /^Nombre de la sesión$/ }).boundingBox();
  expect(nameBounds!.y).toBeGreaterThan(labelBounds!.y + labelBounds!.height);
  expect(nameBounds!.height).toBeLessThanOrEqual(44);
  expect(nameBounds!.width).toBeLessThan(800);
  const captureBounds = await page.getByRole("region", { name: "Dispositivo de captura" }).boundingBox();
  const sessionBounds = await page.getByRole("region", { name: "Datos del análisis" }).boundingBox();
  expect(Math.abs(captureBounds!.y - sessionBounds!.y)).toBeLessThan(2);
  expect(sessionBounds!.x).toBeGreaterThan(captureBounds!.x + captureBounds!.width);
  expect(sessionBounds!.x + sessionBounds!.width).toBeLessThanOrEqual(1168);
  await page.getByRole("button", { name: "Entradas / Salidas", exact: true }).click();
  await expect(page.getByRole("button", { name: "Entradas / Salidas", exact: true })).toHaveAttribute("aria-pressed", "true");
  await page.screenshot({ path: "test-results/webcam-preparation.png", fullPage: true });
  await page.getByRole("button", { name: "Activar modo oscuro" }).click();
  await expect(page.locator("body")).toHaveCSS("background-color", "rgb(20, 24, 27)");
  await expect(page.locator("form")).toHaveCSS("background-color", "rgb(29, 30, 34)");
  await expect(page.getByRole("button", { name: "Actualizar dispositivos" })).toHaveCSS("background-color", "rgb(20, 24, 27)");
  await page.screenshot({ path: "test-results/webcam-preparation-dark.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.getByText("+ Agregar nueva ubicación", { exact: true }).click();
  await expect(page.getByLabel("Nombre de la ubicación", { exact: true })).toBeVisible();
  await page.screenshot({ path: "test-results/webcam-preparation-mobile.png", fullPage: true });
});
const summary = { shop_id: "shop-1", shop_name: "Local", entry_count: 6, exit_count: 3,
  a_to_b_count: 6, b_to_a_count: 3, total_crossings: 9, label_mode: "access", partial: true, entry_direction: "a_to_b" };
const minute = { shop_id: "shop-1", bucket_index: 0, start_seconds: 0, end_seconds: 60,
  entries: 2, exits: 1, observed_seconds: 60, missing_seconds: 0, pending_count: 0,
  is_open: false, coverage_incomplete: false, unknown_tail: false, revision: 2 };
const result = { job_id: "job-1", session_id: "session-1", source_kind: "webcam", status: "processing",
  capture_status: "connected", result_complete: false, coverage_complete: true, unknown_tail: false,
  capture_started_at: "2026-10-05T20:21:00Z", elapsed_capture_seconds: 125, revision: 2,
  checkpoint_at: "2026-10-05T20:23:05Z", selected_shop_id: "shop-1", shops: [summary], summary,
  minutes: [minute, { ...minute, bucket_index: 1, start_seconds: 60, end_seconds: 120,
    entries: 4, exits: 2 }], next_bucket_cursor: null, interruptions: [],
  observed_seconds: 125, missing_seconds: 0, unconfirmed_crossings: 0,
  zone_dwell: { "shop-1": { interior_average_seconds: 12.5, interior_sample_count: 3,
    front_average_seconds: 7, front_sample_count: 2 } },
  sampling: { time_basis: "capture", sample_count: 2, candidate_count: 2, capacity: 20000 } };
const image = "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";

test("preparación del análisis: imagen de referencia, encuadre y zonas", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  const session = { id: "session-1", name: "Entrada del evento", source_kind: "webcam", camera,
    camera_id: camera.id, created_at: camera.created_at, video: null, duplicate_session_ids: [],
    reference_frame: { frame_index: 0, video_timestamp_seconds: 0, width: 320, height: 180,
      url: "/sessions/session-1/reference-frame" } };
  await page.route("**/sessions/session-1", route => route.fulfill({ json: session }));
  await page.route("**/cameras/camera-1/scene-versions", route => route.fulfill({ json: [] }));
  await page.route("**/sessions/session-1/reference-frame", route => route.fulfill({ contentType: "image/svg+xml", body:
    '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180"><rect width="320" height="180" fill="#1c4654"/><text x="40" y="90" fill="white">Entrada del evento</text></svg>' }));
  await page.route("**/sessions/session-1/live/check", route => route.fulfill({ json: {
    check_token: "token", expires_in_seconds: 60, width: 320, height: 180,
    image_media_type: "image/jpeg", image_base64: image, backend: "dshow" } }));
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/sessions/session-1/live");
  await expect(page.getByRole("img", { name: "Imagen de referencia de la webcam" })).toBeVisible();
  await expect(page.getByText("Todavía no hay configuraciones.", { exact: false })).toBeVisible();
  const preview = await page.getByRole("region", { name: "Imagen de referencia" }).boundingBox();
  const settings = await page.getByRole("region", { name: "Preparar el análisis" }).boundingBox();
  expect(settings!.x).toBeGreaterThan(preview!.x + preview!.width);
  expect(settings!.x + settings!.width).toBeGreaterThan(1400);
  for (const height of [768, 720, 640]) {
    await page.setViewportSize({ width: 1366, height });
    expect(await page.evaluate(() => document.documentElement.scrollHeight <= window.innerHeight)).toBe(true);
    const launch = await page.getByRole("button", { name: "Iniciar análisis en vivo" }).boundingBox();
    expect(launch!.y + launch!.height).toBeLessThanOrEqual(height);
  }
  await page.screenshot({ path: "test-results/live-preparation-reference.png", fullPage: true });
  await page.getByRole("button", { name: "Comprobar encuadre" }).click();
  await expect(page.getByRole("img", { name: "Comprobación actual del encuadre de la webcam" })).toBeVisible();
  await page.getByRole("checkbox", { name: "Confirmo que este es el encuadre actual" }).check();
  await expect(page.getByRole("button", { name: "Iniciar análisis en vivo" })).toBeDisabled();
  expect(await page.evaluate(() => document.documentElement.scrollHeight <= window.innerHeight)).toBe(true);
  await page.screenshot({ path: "test-results/live-preparation-checked.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: "test-results/live-preparation-mobile.png", fullPage: true });
  await page.getByRole("link", { name: "Editar escena / polígonos", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Zonas configuradas" })).toBeVisible();
  await page.getByRole("button", { name: "Agregar zona", exact: true }).click();
  await page.getByLabel("Nombre de la zona").fill("Acceso al evento");
  await page.getByText("Agregar áreas y accesos", { exact: true }).click();
  await expect(page.getByRole("button", { name: "Dibujar área" })).toBeVisible();
  await expect(page.getByLabel("Tipo de área nueva").getByRole("option", { name: "Externa", exact: true })).toHaveCount(1);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({ path: "test-results/scene-zones.png", fullPage: true });
});

test("guarda, vuelve atrás y reabre una escena con áreas opcionales nulas", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  let saved: SceneVersion | null = null;
  const session = { id: "session-1", name: "Prueba de reapertura", source_kind: "webcam", camera,
    camera_id: camera.id, created_at: camera.created_at, video: null, duplicate_session_ids: [],
    reference_frame: { frame_index: 0, video_timestamp_seconds: 0, width: 320, height: 180,
      url: "/sessions/session-1/reference-frame" } };
  await page.route("**/sessions/session-1", route => route.fulfill({ json: session }));
  await page.route("**/sessions/session-1/reference-frame", route => route.fulfill({ contentType: "image/jpeg", body: Buffer.from(image, "base64") }));
  await page.route("**/cameras/camera-1/scene-versions", async route => {
    if (route.request().method() === "POST") {
      const payload = route.request().postDataJSON() as SceneVersionCreate;
      saved = { id: "scene-1", camera_id: camera.id, version_number: (saved?.version_number ?? 0) + 1,
        reference_session_id: session.id, frame_width: 320, frame_height: 180,
        created_by_machine_id: null, created_at: camera.created_at, shop_count: payload.shops.length,
        shops: payload.shops.map(shop => ({ shop_id: shop.shop_id ?? "shop-1", name: shop.name,
          zones: { front: shop.zones.front ?? null, interior: shop.zones.interior ?? null, showcase: shop.zones.showcase ?? null },
          entry_line: shop.entry_line! })) };
      await route.fulfill({ json: { ...saved, warnings: [] } });
    } else await route.fulfill({ json: saved ? [saved] : [] });
  });
  await page.route("**/scene-versions/scene-1", route => route.fulfill({ json: saved }));
  await page.goto("/sessions/session-1/live");
  await page.getByRole("link", { name: "Editar escena / polígonos", exact: true }).click();
  await page.getByRole("button", { name: "Agregar zona", exact: true }).click();
  await page.getByLabel("Nombre de la zona").fill("Entrada");
  await page.getByText("Agregar áreas y accesos", { exact: true }).click();
  await page.getByRole("button", { name: "Dibujar área", exact: true }).click();
  for (let i = 0; i < 3; i++) await page.getByRole("button", { name: "Agregar vértice", exact: true }).click();
  await page.getByRole("button", { name: "Cerrar polígono", exact: true }).click();
  await page.getByRole("button", { name: "Crear línea de entrada", exact: true }).click();
  await page.getByRole("button", { name: "Agregar vértice", exact: true }).click();
  await page.getByRole("button", { name: "Agregar vértice", exact: true }).click();
  await page.getByRole("button", { name: "Guardar configuración", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Se guardó la configuración 1.");
  await page.goBack();
  await page.getByRole("link", { name: "Editar escena / polígonos", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Zonas configuradas", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Vértice 1 de área externa de Entrada", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Entrada", exact: true }).click();
  await page.getByLabel("Nombre de la zona").fill("Entrada editada");
  await page.getByRole("button", { name: "Guardar configuración", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Se guardó la configuración 2.");
  expect(errors).toEqual([]);
});

test("estadísticas webcam: hora real, estadías, mapa opcional y duración del historial", async ({ page }) => {
  await page.route("**/sessions/session-1", route => route.fulfill({ json: { id: "session-1", name: "Entrada del evento", camera } }));
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("**/jobs/job-1/live-results?*", (route) => route.fulfill({ json: result }));
  await page.route("**/jobs/job-1/position-samples", (route) => route.fulfill({ json: {
    job_id: "job-1", source_kind: "webcam", time_basis: "capture", availability: "available",
    samples: [{ capture_timestamp_seconds: 1, foot: [.2, .8] }, { capture_timestamp_seconds: 2, foot: [.6, .5] }],
  } }));
  await page.routeWebSocket("**/ws/jobs/job-1/preview", (socket) => {
    socket.onMessage(() => socket.send(JSON.stringify({ type: "live.update", schema_version: "3",
      source_kind: "webcam", job_id: "job-1", session_id: "session-1", revision: 3,
      capture_sequence: 100, segment_index: 0, capture_status: "connected", capture_timestamp_seconds: 125,
      captured_monotonic_ms: 1000, published_monotonic_ms: 1100, image_media_type: "image/jpeg",
      image_base64: image, partial: true, capture_fps: 30, analysis_fps: 10, capture_to_publish_ms: 100,
      shops: [summary], minutes: result.minutes, coverage_complete: true, checkpoint_revision: 2,
      checkpoint_at: result.checkpoint_at, capture_started_at: result.capture_started_at, zone_dwell: result.zone_dwell,
    })));
  });
  await page.goto("/live/jobs/job-1");
  await expect(page.getByRole("img", { name: "Cámara en vivo", exact: true })).toBeVisible();
  await expect(page.getByText("Cámara de prueba · Entrada del evento", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Estadía promedio interna", { exact: true })).toHaveText("12,5 s");
  await expect(page.getByLabel("Estadía promedio externa", { exact: true })).toHaveText("7 s");
  await page.setViewportSize({ width: 1366, height: 768 });
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollHeight <= window.innerHeight)).toBe(true);
  await expect(page.getByText(/Última sincronización:/)).toBeInViewport();
  await page.getByText("Ver datos y cobertura", { exact: true }).click();
  await expect(page.getByRole("rowheader", { name: "17:21", exact: true })).toBeVisible();
  await expect(page.locator(".recharts-line")).toHaveCount(2);
  await expect(page.locator(".recharts-wrapper").getByText(/^17:2[12]$/)).toHaveText(["17:21", "17:22"]);
  await expect(page.getByRole("img", { name: "Mapa de calor", exact: true })).toHaveCount(0);
  await page.getByRole("switch", { name: "Superponer mapa de calor" }).check();
  await expect(page.getByRole("img", { name: "Mapa de calor", exact: true })).toBeVisible();
  await page.getByRole("heading", { name: "Monitoreo en vivo", exact: true }).click();
  await page.screenshot({ path: "test-results/live-statistics.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByLabel("Estadía promedio interna", { exact: true })).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: "test-results/live-statistics-mobile.png", fullPage: true });
  await page.getByRole("switch", { name: "Superponer mapa de calor" }).uncheck();
  await expect(page.getByRole("img", { name: "Mapa de calor", exact: true })).toHaveCount(0);
  await page.route("**/sessions", (route) => route.fulfill({ json: [
    { id: "session-1", name: "Webcam de prueba", source_kind: "webcam", camera, created_at: camera.created_at },
  ] }));
  await page.route("**/processed-sessions", (route) => route.fulfill({ json: [
    { session_id: "session-1", job_id: "job-1", status: "completed", result_complete: true, live_duration_seconds: 3661 },
  ] }));
  await page.getByRole("navigation", { name: "Principal" }).getByRole("link", { name: "Mis análisis", exact: true }).click();
  await expect(page.getByRole("row").filter({ hasText: "Webcam de prueba" })).toContainText("Tiempo analizado: 01:01:01");
  expect(errors).toEqual([]);
});

test("consola webcam finalizada: reporte, cobertura y horarios legibles", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.route("**/jobs/job-1/live-results?*", route => route.fulfill({ json: {
    ...result, status: "completed", capture_status: "stopped", result_complete: true, coverage_complete: false, zone_dwell: {},
  } }));
  await page.route("**/sessions/session-1", route => route.fulfill({ json: { id: "session-1", name: "Entrada del evento", camera } }));
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto("/live/jobs/job-1");
  await expect(page.getByText("Transmisión detenida", { exact: true })).toBeVisible();
  await expect(page.getByText("Conexión WebSocket cerrada", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Detener análisis" })).toBeDisabled();
  await expect(page.getByRole("link", { name: "Ver reporte completo" })).toHaveAttribute("href", "/live/jobs/job-1/results");
  await expect(page.getByLabel("Estadía promedio interna", { exact: true })).toHaveText("--");
  await expect(page.getByText(/Última sincronización:/)).toHaveText(/Última sincronización: \d{2}:\d{2}:\d{2} hs/);
  await expect(page.getByText("Cobertura incompleta: hubo intervalos sin analizar.", { exact: true })).toBeVisible();
  for (const viewport of [{ width: 1920, height: 900 }, { width: 1366, height: 768 }]) {
    await page.setViewportSize(viewport);
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollHeight <= window.innerHeight)).toBe(true);
    await expect(page.getByText(/Última sincronización:/)).toBeInViewport();
    const panel = page.getByRole("complementary", { name: "Estadísticas en vivo" });
    await expect.poll(() => panel.evaluate(element => element.scrollHeight <= element.clientHeight)).toBe(true);
  }
  await page.screenshot({ path: "test-results/live-console-ended.png", fullPage: true });
});

test("etiquetas de webcam: selección Entrada/Salida, editor, vivo y reporte", async ({ page }) => {
  const liveSource = { machine_id: "local", device_index: 0, capture_backend: "fake", width: 320, height: 180,
    reported_fps: 30, label_mode: "access", prepared_at: camera.created_at, frame_checked_at: null };
  const detail = { id: "session-1", name: "Acceso", source_kind: "webcam", camera,
    created_at: camera.created_at, video: null, duplicate_session_ids: [], live_source: liveSource,
    reference_frame: { frame_index: 0, video_timestamp_seconds: 0, width: 320, height: 180, url: "/sessions/session-1/reference-frame" } };
  const scene = { id: "scene-1", camera_id: camera.id, version_number: 1, reference_session_id: detail.id,
    frame_width: 320, frame_height: 180, shop_count: 1, created_at: camera.created_at,
    shops: [{ shop_id: "shop-1", name: "Acceso", zones: { front: [[.1,.1],[.9,.1],[.5,.4]] },
      entry_line: { start: [.2,.5], end: [.8,.5], entry_direction: "b_to_a" } }] };
  let mode: string | undefined;
  await page.route("**/cameras", route => route.fulfill({ json: [camera] }));
  await page.route("**/live/devices", route => route.fulfill({ json: { machine_id: "local", worker_available: true,
    candidates: [{ device_index: 0, label: "Webcam de prueba", verified: false }] } }));
  await page.route("**/live/sessions", route => {
    mode = (route.request().postDataJSON() as { label_mode: string }).label_mode;
    return route.fulfill({ json: detail });
  });
  await page.route("**/sessions/session-1", route => route.fulfill({ json: detail }));
  await page.route("**/sessions/session-1/reference-frame", route => route.fulfill({ contentType: "image/jpeg", body: Buffer.from(image, "base64") }));
  await page.route("**/cameras/camera-1/scene-versions", route => route.fulfill({ json: [scene] }));
  await page.route("**/scene-versions/scene-1", route => route.fulfill({ json: scene }));
  await page.route("**/processed-sessions", route => route.fulfill({ json: [] }));
  const accessSummary = { ...summary, label_mode: "access", entry_direction: "b_to_a", a_to_b_count: 3, b_to_a_count: 6 };
  await page.route("**/jobs/job-1/live-results?*", route => route.fulfill({ json: { ...result, summary: accessSummary } }));
  await page.routeWebSocket("**/ws/jobs/job-1/preview", () => {});
  await page.route("**/jobs/job-1/position-samples", route => route.fulfill({ json: { job_id: "job-1", source_kind: "webcam", time_basis: "capture", availability: "unavailable", samples: [] } }));
  await page.route("**/jobs/job-1/live-events?*", route => route.fulfill({ json: { events: [
    { id: "e-1", track_id: 1, capture_timestamp_seconds: 1, confirmed_at_capture_seconds: 2, direction: "entry" },
    { id: "e-2", track_id: 2, capture_timestamp_seconds: 3, confirmed_at_capture_seconds: 4, direction: "exit" },
  ], next_cursor: null } }));
  await page.goto("/live");
  await page.getByRole("button", { name: "Entradas / Salidas", exact: true }).click();
  await page.getByLabel("Nombre de la sesión", { exact: true }).fill("Acceso");
  await page.getByLabel("Ubicación asignada", { exact: true }).selectOption(camera.id);
  await page.getByRole("button", { name: "Preparar webcam y continuar", exact: true }).click();
  await expect(page).toHaveURL(/\/sessions\/session-1\/live$/);
  expect(mode).toBe("access");
  await page.getByRole("link", { name: "Editar escena / polígonos" }).click();
  await expect(page.getByRole("img", { name: "Lado de entrada de Acceso", exact: true })).toHaveText("Entrada");
  await page.getByRole("button", { name: "Línea de entrada", exact: true }).click();
  await expect(page.getByRole("button", { name: "Invertir entrada y salida" })).toBeVisible();
  await expect(page.getByRole("button", { name: "B → A es entrada" })).toHaveCount(0);
  await page.goto("/live/jobs/job-1");
  await expect(page.getByLabel("Entradas", { exact: true })).toHaveText("6");
  await expect(page.getByLabel("Salidas", { exact: true })).toHaveText("3");
  await page.getByRole("link", { name: "Ver reporte completo" }).click();
  await expect(page.getByText("Entradas: 6 · Salidas: 3", { exact: true })).toBeVisible();
  await page.getByText("Diagnóstico técnico de la captura (Interrupciones y descarte)", { exact: true }).click();
  await expect(page.getByRole("cell", { name: "Entrada", exact: true })).toBeVisible();
  await expect(page.getByRole("cell", { name: "Salida", exact: true })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Entradas", exact: true })).toHaveCount(1);
  await expect(page.getByRole("columnheader", { name: "Salidas", exact: true })).toHaveCount(1);
});
