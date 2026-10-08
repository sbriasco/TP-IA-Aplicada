import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { startWorker, stopWorker } from "./support";

const currentDirectory = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(currentDirectory, "../..");
const API = process.env.FLOWSIGHT_E2E_API_URL ?? "http://127.0.0.1:8000";

test("la vista de un video muestra el fotograma y el instante del mensaje", async ({
  page,
  request,
}) => {
  test.setTimeout(60_000);
  const clipPath = process.env.FLOWSIGHT_E2E_CLIP;
  if (clipPath === undefined || clipPath === "") {
    throw new Error("Falta FLOWSIGHT_E2E_CLIP: correr con `npm run test:e2e`.");
  }

  const cameraName = `e2e-vista-${Date.now()}`;
  const cameraResponse = await request.post(`${API}/cameras`, { data: { name: cameraName } });
  expect(cameraResponse.ok()).toBeTruthy();
  const camera = (await cameraResponse.json()) as { id: string };

  const sessionResponse = await request.post(
    `${API}/video-sessions?name=${encodeURIComponent("Vista e2e")}&registered_camera_id=${camera.id}&filename=clip.avi`,
    {
      data: fs.readFileSync(clipPath),
      headers: { "content-type": "application/octet-stream" },
    },
  );
  expect(sessionResponse.ok()).toBeTruthy();
  const session = (await sessionResponse.json()) as { id: string };

  const sceneResponse = await request.post(`${API}/cameras/${camera.id}/scene-versions`, {
    data: {
      reference_session_id: session.id,
      shops: [
        {
          name: "Local",
          zones: {
            front: [
              [0.1, 0.2],
              [0.9, 0.2],
              [0.9, 0.8],
              [0.1, 0.8],
            ],
          },
          entry_line: {
            start: [0.2, 0.5],
            end: [0.8, 0.5],
            entry_direction: "a_to_b",
          },
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

  await page.addInitScript(() => {
    const target = window as Window & { __previewTimestamp?: number };
    const NativeWebSocket = window.WebSocket;
    window.WebSocket = class extends NativeWebSocket {
      constructor(url: string | URL, protocols?: string | string[]) {
        if (protocols === undefined) {
          super(url);
        } else {
          super(url, protocols);
        }
        this.addEventListener("message", (event) => {
          const message = JSON.parse(String(event.data)) as {
            type: string;
            video_timestamp_seconds?: number;
          };
          if (message.type === "preview.update" && message.video_timestamp_seconds !== undefined) {
            target.__previewTimestamp = message.video_timestamp_seconds;
          }
        });
      }
    };
  });

  const worker = startWorker(root);
  try {
    await page.goto(`/?job=${job.id}`);
    await expect(page.getByRole("img", { name: /Previsualización del frame/ })).toBeVisible({
      timeout: 30_000,
    });
    await expect
      .poll(
        async () => {
          const timestamp = await page.evaluate(
            () => (window as Window & { __previewTimestamp?: number }).__previewTimestamp,
          );
          return timestamp !== undefined && page.getByText(`${timestamp} s`, { exact: true }).isVisible();
        },
        { timeout: 30_000 },
      )
      .toBe(true);
    await expect(page.getByText("no promete la velocidad del video")).toBeVisible();
  } finally {
    stopWorker(worker);
  }
});

test("cancelar un análisis pendiente lo deja cancelado e incompleto", async ({ page, request }) => {
  const clipPath = process.env.FLOWSIGHT_E2E_CLIP;
  if (clipPath === undefined || clipPath === "") {
    throw new Error("Falta FLOWSIGHT_E2E_CLIP: correr con `npm run test:e2e`.");
  }

  const cameraName = `e2e-cancel-${Date.now()}`;
  const cameraResponse = await request.post(`${API}/cameras`, { data: { name: cameraName } });
  expect(cameraResponse.ok()).toBeTruthy();
  const camera = (await cameraResponse.json()) as { id: string };

  const sessionResponse = await request.post(
    `${API}/video-sessions?name=${encodeURIComponent("Cancelar e2e")}&registered_camera_id=${camera.id}&filename=clip.avi`,
    {
      data: fs.readFileSync(clipPath),
      headers: { "content-type": "application/octet-stream" },
    },
  );
  expect(sessionResponse.ok()).toBeTruthy();
  const session = (await sessionResponse.json()) as { id: string };

  const sceneResponse = await request.post(`${API}/cameras/${camera.id}/scene-versions`, {
    data: {
      reference_session_id: session.id,
      shops: [
        {
          name: "Local",
          zones: {
            front: [
              [0.1, 0.2],
              [0.9, 0.2],
              [0.9, 0.8],
              [0.1, 0.8],
            ],
          },
          entry_line: {
            start: [0.2, 0.5],
            end: [0.8, 0.5],
            entry_direction: "a_to_b",
          },
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

  await page.goto(`/?job=${job.id}`);
  await page.getByRole("button", { name: "Cancelar análisis" }).click();
  await expect(page.getByText("incompleto")).toBeVisible();
  await expect(page.getByText("cancelled", { exact: true })).toBeVisible();

  const after = await request.get(`${API}/jobs/${job.id}`);
  expect(after.ok()).toBeTruthy();
  expect(((await after.json()) as { status: string }).status).toBe("cancelled");
});
