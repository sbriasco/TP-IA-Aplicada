import { expect, test, type APIRequestContext } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { startWorker, stopWorker } from "./support";

const currentDirectory = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(currentDirectory, "../..");
const API = "http://127.0.0.1:8000";

test("en resultados se pregunta, se ve la espera y otra sesión deja el panel vacío", async ({
  page,
  request,
}) => {
  const clipPath = process.env.FLOWSIGHT_E2E_CLIP;
  if (clipPath === undefined || clipPath === "") {
    throw new Error("Falta FLOWSIGHT_E2E_CLIP: correr con `npm run test:e2e`.");
  }

  const stamp = Date.now();
  const firstName = `Chat e2e ${stamp}`;
  const secondName = `Otra e2e ${stamp}`;
  const cameraResponse = await request.post(`${API}/cameras`, { data: { name: `e2e-chat-${stamp}` } });
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

  await page.route("**/chat", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 600));
    await route.continue();
  });

  await page.goto("/");
  const history = page.getByRole("region", { name: "Sesiones procesadas" });
  await history.getByRole("link", { name: firstName }).click();
  await expect(page.getByRole("heading", { name: firstName })).toBeVisible();
  await page.getByLabel("Pregunta").fill("¿cuál es el tráfico?");
  await page.getByRole("button", { name: "Enviar" }).click();
  await expect(page.getByText("Consultando")).toBeVisible();

  const answer = page.getByRole("region", { name: "Respuesta" });
  await expect(answer).toContainText("Local");
  await expect(answer).toContainText("toda la sesión");

  await page.goto("/");
  await history.getByRole("link", { name: secondName }).click();
  await expect(page.getByRole("heading", { name: secondName })).toBeVisible();
  await expect(page.getByRole("region", { name: "Respuesta" })).toHaveCount(0);
  await expect(page.getByLabel("Pregunta")).toHaveValue("");
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
): Promise<{ jobId: string }> {
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
  const scene = (await sceneResponse.json()) as { id: string };
  const jobResponse = await request.post(`${API}/sessions/${session.id}/jobs`, {
    data: { kind: "video_analysis", scene_version_id: scene.id },
  });
  expect(jobResponse.ok()).toBeTruthy();
  const job = (await jobResponse.json()) as { id: string };
  return { jobId: job.id };
}
