import { expect, test } from "@playwright/test";

test("dashboard claro y oscuro: búsqueda, filtros, tema persistido y acciones", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.emulateMedia({ colorScheme: "light" });
  const camera = { id: "camera-1", name: "Entrada Evento", created_at: "2026-10-05T20:21:00Z" };
  const sessions = [
    { id: "session-1", name: "Prueba", source_kind: "webcam", camera, created_at: camera.created_at },
    { id: "session-2", name: "Dentro", source_kind: "video_file", camera: { ...camera, name: "Pasillo norte" }, created_at: "2026-10-02T20:00:00Z" },
    { id: "session-3", name: "Acceso en vivo", source_kind: "webcam", camera, created_at: camera.created_at },
  ];
  await page.route("**/sessions", route => route.fulfill({ json: sessions }));
  await page.route("**/processed-sessions", route => route.fulfill({ json: [
    { session_id: "session-1", job_id: "job-1", status: "completed", result_complete: true, live_duration_seconds: 112 },
    { session_id: "session-2", job_id: "job-2", status: "completed", result_complete: true },
    { session_id: "session-3", job_id: "job-3", status: "processing", result_complete: false, live_duration_seconds: 25 },
  ] }));
  await page.route("**/cameras", route => route.fulfill({ json: [camera] }));
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Tus análisis" })).toBeVisible();
  await expect(page.getByRole("row").filter({ has: page.getByRole("link", { name: "Prueba", exact: true }) })).toContainText("Tiempo analizado: 00:01:52");
  await expect(page.getByRole("button", { name: "Eliminar Acceso en vivo" })).toBeDisabled();
  await expect(page.getByRole("complementary", { name: "Guía de estados" })).toHaveCount(0);
  expect((await page.getByRole("searchbox", { name: "Buscar análisis" }).boundingBox())!.height).toBeLessThanOrEqual(34);
  await page.screenshot({ path: "test-results/dashboard-light.png", fullPage: true });
  await page.getByRole("button", { name: "Activar modo oscuro" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.reload();
  await expect(page.getByRole("button", { name: "Activar modo claro" })).toBeVisible();
  await page.screenshot({ path: "test-results/dashboard-dark.png", fullPage: true });
  await page.getByRole("button", { name: "Activos", exact: true }).click();
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await expect(page.locator("tbody")).toContainText("Acceso en vivo");
  await page.getByRole("searchbox", { name: "Buscar análisis" }).fill("norte");
  await expect(page.getByText("No hay análisis que coincidan", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Completados", exact: true }).click();
  await expect(page.locator("tbody")).toContainText("Dentro");
  await page.getByRole("searchbox", { name: "Buscar análisis" }).fill("");
  await page.getByRole("button", { name: "Todos", exact: true }).click();
  await page.getByRole("button", { name: "Nuevo análisis", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Nuevo análisis" })).toBeVisible();
  await page.getByRole("button", { name: "Cerrar", exact: true }).click();
  await page.getByRole("button", { name: "Cámaras", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Administrar cámaras" })).toBeVisible();
  await page.getByRole("button", { name: "Cerrar", exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: "test-results/dashboard-mobile-dark.png", fullPage: true });
  await page.getByRole("button", { name: "Activar modo claro" }).click();
  await page.screenshot({ path: "test-results/dashboard-mobile-light.png", fullPage: true });
  expect(errors).toEqual([]);
});
