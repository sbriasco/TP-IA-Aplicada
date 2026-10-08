import { expect, test, type APIRequestContext } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { startWorker, stopWorker } from "./support";

const currentDirectory = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(currentDirectory, "../..");

const API = process.env.FLOWSIGHT_E2E_API_URL ?? "http://127.0.0.1:8000";

test("el historial abre los indicadores de esa sesión y conserva el frame sin el video", async ({
  page,
  request,
}) => {
  const clipPath = process.env.FLOWSIGHT_E2E_CLIP;
  const videosDir = process.env.FLOWSIGHT_VIDEOS_DIR;
  if (clipPath === undefined || clipPath === "" || videosDir === undefined || videosDir === "") {
    throw new Error("Falta FLOWSIGHT_E2E_CLIP o FLOWSIGHT_VIDEOS_DIR: correr con `npm run test:e2e`.");
  }

  const stamp = Date.now();
  const firstName = `Primera e2e ${stamp}`;
  const secondName = `Segunda e2e ${stamp}`;
  const cameraResponse = await request.post(`${API}/cameras`, { data: { name: `e2e-resultados-${stamp}` } });
  expect(cameraResponse.ok()).toBeTruthy();
  const camera = (await cameraResponse.json()) as { id: string };
  const first = await registerSession(request, camera.id, firstName, clipPath);
  const second = await registerSession(request, camera.id, secondName, clipPath);

  test.setTimeout(120_000);
  const worker = startWorker(root);
  try {
    await expect
      .poll(async () => (await jobStatus(request, first.jobId)) === "completed", { timeout: 90_000 })
      .toBeTruthy();
    await expect
      .poll(async () => (await jobStatus(request, second.jobId)) === "completed", { timeout: 90_000 })
      .toBeTruthy();
  } finally {
    stopWorker(worker);
  }

  const metricsResponse = await request.get(
    `${API}/sessions/${first.sessionId}/shops/${first.shopId}/metrics`,
  );
  expect(metricsResponse.ok()).toBeTruthy();
  const metrics = (await metricsResponse.json()) as {
    metrics: { code: string; value: number | null }[];
  };
  const traffic = metrics.metrics.find((metric) => metric.code === "traffic_total");

  await page.goto("/");
  const history = page.getByRole("region", { name: "Historial de análisis" });
  await expect(history.getByRole("link", { name: firstName })).toBeVisible();
  await expect(history.getByRole("link", { name: secondName })).toBeVisible();
  await history.getByRole("row").filter({ has: page.getByRole("link", { name: firstName, exact: true }) }).getByRole("link", { name: "Ver resultados" }).click();
  await expect(page.getByRole("heading", { name: firstName })).toBeVisible();
  await expect(page.getByText(secondName)).toHaveCount(0);
  const indicators = page.getByRole("region", { name: "Indicadores de la sesión" });
  await expect(indicators).toContainText("Tráfico estimado");
  if (traffic?.value != null) {
    await expect(indicators).toContainText(
      new Intl.NumberFormat("es-AR", { maximumFractionDigits: 2 }).format(traffic.value),
    );
  }
  await expect(page.getByText("Cargando gráfico…", { exact: true })).toHaveCount(0);

  for (const viewport of [{ width: 1280, height: 720 }, { width: 1024, height: 768 }]) {
    await page.setViewportSize(viewport);
    await expect(page.getByRole("heading", { name: "Agente FlowSight" })).toBeVisible();
    const composer = await page.getByLabel("Pregunta al agente", { exact: true }).boundingBox();
    expect(composer).not.toBeNull();
    expect(composer!.y + composer!.height).toBeLessThanOrEqual(viewport.height);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  }
  await page.getByRole("button", { name: "¿Cuál fue el horario pico?", exact: true }).click();
  await expect(page.getByLabel("Pregunta al agente", { exact: true })).toHaveValue("¿Cuál fue el horario pico?");
  await page.getByLabel("Cómo se mide Tráfico", { exact: true }).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.screenshot({ path: "../.verification/frontend-redesign/resultados-compactos-1024.png" });
  await page.getByLabel("Cómo se mide Tráfico", { exact: true }).click();
  await page.setViewportSize({ width: 1280, height: 720 });
  await expect(page.getByText("Cargando gráfico…", { exact: true })).toHaveCount(0);
  await page.screenshot({ path: "../.verification/frontend-redesign/resultados-compactos-1280.png" });

  const detail = await request.get(`${API}/sessions/${first.sessionId}`);
  const relative = ((await detail.json()) as { video: { relative_path: string } }).video.relative_path;
  fs.rmSync(path.join(videosDir, relative), { force: true });
  await page.reload();
  await expect(page.getByText("El archivo no está en este equipo.")).toHaveCount(0);
  await expect(page.getByRole("img", { name: "Frame de referencia" })).toBeVisible();
});

async function jobStatus(request: APIRequestContext, jobId: string): Promise<string> {
  const response = await request.get(`${API}/jobs/${jobId}`);
  return (await response.json()).status;
}

async function registerSession(
  request: APIRequestContext,
  cameraId: string,
  name: string,
  clipPath: string,
): Promise<{ sessionId: string; jobId: string; shopId: string }> {
  const sessionResponse = await request.post(
    `${API}/video-sessions?name=${encodeURIComponent(name)}&registered_camera_id=${cameraId}&filename=clip.avi`,
    { data: fs.readFileSync(clipPath), headers: { "content-type": "application/octet-stream" } },
  );
  expect(sessionResponse.ok()).toBeTruthy();
  const session = (await sessionResponse.json()) as { id: string };
  const sceneResponse = await request.post(`${API}/cameras/${cameraId}/scene-versions`, {
    data: {
      reference_session_id: session.id,
      shops: [
        {
          name: "Local",
          zones: {
            front: [
              [0.0, 0.0],
              [1, 0.0],
              [1, 1],
              [0.0, 1],
            ],
          },
          entry_line: { start: [0.1, 0.9], end: [0.9, 0.9], entry_direction: "a_to_b" },
        },
      ],
    },
  });
  expect(sceneResponse.ok()).toBeTruthy();
  const scene = (await sceneResponse.json()) as { id: string; shops: { shop_id: string }[] };
  const jobResponse = await request.post(`${API}/sessions/${session.id}/jobs`, {
    data: { kind: "video_analysis", scene_version_id: scene.id },
  });
  expect(jobResponse.ok()).toBeTruthy();
  const job = (await jobResponse.json()) as { id: string };
  return { sessionId: session.id, jobId: job.id, shopId: scene.shops[0].shop_id };
}
