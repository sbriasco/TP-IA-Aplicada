import { expect, test, type Page } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { startWorker, stopWorker } from "./support";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const API = process.env.FLOWSIGHT_E2E_API_URL ?? "http://127.0.0.1:8000";
async function point(page: Page, x: number, y: number) {
  const position = await page.getByRole("group", { name: "Frame de referencia con la escena" }).evaluate((element, [px, py]) => {
    const matrix = (element as SVGSVGElement).getScreenCTM();
    if (!matrix) throw new Error("El frame no tiene matriz.");
    return [matrix.a * px + matrix.c * py + matrix.e, matrix.b * px + matrix.d * py + matrix.f];
  }, [x, y]);
  await page.mouse.click(position[0], position[1]);
}

for (const recover of [false, true]) {
test(`webcam fake: preparación, editor, vivo, ${recover ? "recuperación confirmada, " : ""}reload, stop e historial sin grabación`, async ({ page, request }) => {
  test.setTimeout(180000);
  const worker = startWorker(root, true, recover ? { FLOWSIGHT_LIVE_FAKE_FAIL_AFTER: "300" } : {});
  const errors: string[] = []; page.on("pageerror", (error) => errors.push(error.message));
  try {
    await expect.poll(async () => { const response = await request.get(`${API}/live/devices`);
      return response.ok() && ((await response.json()) as { worker_available: boolean }).worker_available;
    }, { timeout: 60000 }).toBeTruthy();
    const cameraName = `Webcam expo ${Date.now()}`;
    const created = await request.post(`${API}/cameras`, { data: { name: cameraName } });
    expect(created.ok()).toBeTruthy();
    const camera = await created.json() as { id: string };
    await page.goto("/live");
    await page.getByLabel("Nombre de la sesión").fill("Expo webcam");
    await page.getByLabel("Cámara", { exact: true }).selectOption(camera.id);
    await expect(page.getByLabel("Webcam", { exact: true }).getByRole("option", { name: "Webcam simulada (prueba)", exact: true })).toHaveCount(1);
    await page.getByRole("button", { name: "Actualizar dispositivos", exact: true }).click();
    await expect(page.getByRole("button", { name: "Preparar webcam y continuar", exact: true })).toBeEnabled();
    const preparedResponse = page.waitForResponse((response) => response.url().endsWith("/live/sessions") && response.request().method() === "POST");
    await page.getByRole("button", { name: "Preparar webcam y continuar", exact: true }).click();
    expect((await preparedResponse).status()).toBe(201);
    await page.waitForURL(/\/sessions\/[^/]+\/live$/);
    const sessionId = new URL(page.url()).pathname.split("/")[2];
    await page.getByRole("link", { name: "Editar escena / polígonos", exact: true }).click();
    await expect(page.getByRole("group", { name: "Frame de referencia con la escena" })).toBeVisible();
    await page.getByRole("button", { name: "Agregar zona" }).click();
    await page.getByLabel("Nombre de la zona").fill("Paso expo");
    await page.getByLabel("Tipo de área nueva").selectOption("front");
    await page.getByRole("button", { name: "Dibujar área", exact: true }).click();
    for (const [x, y] of [[100, 100], [1100, 100], [1100, 650], [100, 650]]) await point(page, x, y);
    await page.getByRole("button", { name: "Cerrar polígono" }).click();
    await page.getByRole("button", { name: "Crear línea de entrada" }).click();
    await point(page, 100, 360); await point(page, 1100, 360);
    await page.getByRole("button", { name: "Guardar configuración" }).click();
    await expect(page.getByRole("status").filter({ hasText: /Se guardó la configuración/ })).toBeVisible();
    await page.goto(`/sessions/${sessionId}/live`);
    await expect(page.getByRole("button", { name: "Iniciar análisis en vivo" })).toBeDisabled();
    const checkedResponse = page.waitForResponse((response) => response.url().endsWith("/live/check"));
    await page.getByRole("button", { name: "Comprobar encuadre" }).click();
    expect((await checkedResponse).status()).toBe(200);
    await expect(page.getByRole("img", { name: "Comprobación actual del encuadre de la webcam" })).toBeVisible();
    await page.getByLabel("Confirmo que este es el encuadre actual").check();
    await page.getByRole("button", { name: "Iniciar análisis en vivo" }).click();
    await page.waitForURL(/\/live\/jobs\/[^/]+$/);
    const jobId = new URL(page.url()).pathname.split("/")[3];
    await expect(page.getByRole("img", { name: "Cámara en vivo", exact: true })).toBeVisible({ timeout: 20000 });
    await expect(page.getByLabel("Total de cruces", { exact: true })).toHaveText("0");
    await expect(page.getByRole("heading", { name: "Cruces por minuto" })).toBeVisible();
    await page.reload();
    await expect(page.getByRole("img", { name: "Cámara en vivo", exact: true })).toBeVisible();
    if (recover) {
      await expect(page.getByRole("img", { name: "Encuadre para reanudar", exact: true })).toBeVisible({ timeout: 30000 });
      await page.reload();
      await expect(page.getByRole("img", { name: "Encuadre para reanudar", exact: true })).toBeVisible();
      await expect(page.getByRole("button", { name: "Reanudar análisis", exact: true })).toBeDisabled();
      const before = await (await request.get(`${API}/jobs/${jobId}`)).json() as { frames_analyzed: number };
      await page.waitForTimeout(1000);
      const during = await (await request.get(`${API}/jobs/${jobId}`)).json() as { frames_analyzed: number };
      expect(during.frames_analyzed).toBe(before.frames_analyzed);
      await page.getByLabel("Confirmo que el encuadre coincide con la configuración").check();
      const resumedResponse = page.waitForResponse((response) => response.url().endsWith("/live/confirm-resume"));
      await page.getByRole("button", { name: "Reanudar análisis", exact: true }).click();
      expect((await resumedResponse).status()).toBe(202);
      await expect(page.getByRole("img", { name: "Encuadre para reanudar", exact: true })).toHaveCount(0);
      await expect(page.getByRole("img", { name: "Cámara en vivo", exact: true })).toBeVisible();
      const results = await (await request.get(`${API}/jobs/${jobId}/live-results`)).json() as { coverage_complete: boolean; interruptions: unknown[] };
      expect(results.coverage_complete).toBe(false);
      expect(results.interruptions.length).toBeGreaterThan(0);
    }
    await page.getByRole("button", { name: "Detener análisis" }).click();
    await expect(page.getByRole("status")).toHaveText("Análisis finalizado", { timeout: 15000 });
    const job = await request.get(`${API}/jobs/${jobId}`);
    expect((await job.json()) as { status: string }).toMatchObject({ status: "completed", result_complete: true });
    await page.getByRole("link", { name: "Ver resultados guardados" }).click();
    await expect(page.getByRole("heading", { name: "Resultados de webcam" })).toBeVisible();
    await expect(page.getByText(/Sin grabación/).first()).toBeVisible();
    await expect(page.getByRole("img", { name: "Mapa de calor" })).toBeVisible();
    await expect(page.locator("video")).toHaveCount(0);
    await expect(page.getByText("El chat no está disponible para las sesiones de webcam.")).toBeVisible();
    expect(errors).toEqual([]);
  } finally { stopWorker(worker); }
});
}
