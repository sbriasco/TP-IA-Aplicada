import { expect, test } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { startWorker, stopWorker } from "./support";
import type { LiveResults } from "../src/types/live";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const API = process.env.FLOWSIGHT_E2E_API_URL ?? "http://127.0.0.1:8000";

test("webcam: dos pausas, recarga, encuadre confirmado y stop en el mismo trabajo", async ({ page, request }) => {
  test.setTimeout(180000);
  const worker = startWorker(root, true);
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  try {
    await expect.poll(async () => {
      const response = await request.get(`${API}/live/devices`);
      return response.ok() && ((await response.json()) as { worker_available: boolean }).worker_available;
    }, { timeout: 60000 }).toBeTruthy();
    const cameraResponse = await request.post(`${API}/cameras`, { data: { name: `Pausa ${Date.now()}` } });
    expect(cameraResponse.status()).toBe(201);
    const camera = await cameraResponse.json() as { id: string };
    const prepared = await request.post(`${API}/live/sessions`, { data: {
      name: "Monitoreo con pausas", registered_camera_id: camera.id, device_index: 0, label_mode: "access",
    } });
    expect(prepared.status()).toBe(201);
    const session = await prepared.json() as { id: string };
    const sceneResponse = await request.post(`${API}/cameras/${camera.id}/scene-versions`, { data: {
      reference_session_id: session.id, shops: [{ name: "Acceso", zones: {
        front: [[.05,.5],[.95,.5],[.95,.95],[.05,.95]],
        interior: [[.05,.05],[.95,.05],[.95,.5],[.05,.5]],
      }, entry_line: { start: [.05,.5], end: [.95,.5], entry_direction: "a_to_b" } }],
    } });
    expect(sceneResponse.status()).toBe(201);
    const scene = await sceneResponse.json() as { id: string };
    const check = await (await request.post(`${API}/sessions/${session.id}/live/check`)).json() as { check_token: string };
    const started = await request.post(`${API}/sessions/${session.id}/live/start`, { data: {
      scene_version_id: scene.id, check_token: check.check_token, frame_confirmed: true,
    } });
    expect(started.status()).toBe(201);
    const job = await started.json() as { id: string };
    const results = async () => (await (await request.get(`${API}/jobs/${job.id}/live-results`)).json()) as LiveResults;
    await page.goto(`/live/jobs/${job.id}`);
    await expect(page.getByRole("img", { name: "Cámara en vivo", exact: true })).toBeVisible({ timeout: 30000 });
    for (let cycle = 0; cycle < 2; cycle++) {
      await expect.poll(async () => (await results()).capture_status).toBe("connected");
      await page.getByRole("button", { name: "Pausar análisis", exact: true }).click();
      await expect(page.getByRole("button", { name: "Retomar análisis", exact: true })).toBeEnabled();
      const paused = await results();
      expect(paused.status).toBe("processing");
      expect(paused.interruptions.filter(gap => gap.reason === "operator_pause")).toHaveLength(cycle + 1);
      await page.reload();
      await expect(page.getByRole("button", { name: "Retomar análisis", exact: true })).toBeEnabled();
      const unchanged = await results();
      expect(unchanged.summary).toEqual(paused.summary);
      expect(unchanged.zone_dwell).toEqual(paused.zone_dwell);
      expect(unchanged.elapsed_capture_seconds).toBe(paused.elapsed_capture_seconds);
      await expect(page.getByRole("img", { name: "Cámara en vivo", exact: true })).toHaveCount(0);
      await expect(page.getByRole("button", { name: "Detener análisis", exact: true })).toBeEnabled();
      if (cycle === 1) break;
      await page.getByRole("button", { name: "Retomar análisis", exact: true }).click();
      await expect(page.getByRole("img", { name: "Encuadre para reanudar", exact: true })).toBeVisible({ timeout: 15000 });
      await expect(page.getByRole("button", { name: "Reanudar análisis", exact: true })).toBeDisabled();
      await page.getByLabel("Confirmo que el encuadre coincide con la configuración").check();
      await page.getByRole("button", { name: "Reanudar análisis", exact: true }).click();
      await expect(page.getByRole("img", { name: "Cámara en vivo", exact: true })).toBeVisible();
      expect((await results()).job_id).toBe(job.id);
      expect((await results()).session_id).toBe(session.id);
    }
    await page.getByRole("button", { name: "Detener análisis", exact: true }).click();
    await expect(page.getByRole("status")).toHaveText("Análisis finalizado", { timeout: 15000 });
    const final = await results();
    expect(final.status).toBe("completed");
    expect(final.interruptions.filter(gap => gap.reason === "operator_pause" && gap.end_known)).toHaveLength(2);
    expect(final.missing_seconds).toBeGreaterThan(0);
    expect(final.coverage_complete).toBe(false);
    await page.getByRole("link", { name: "Ver reporte completo", exact: true }).click();
    await page.getByText("Diagnóstico técnico de la captura (Interrupciones y descarte)", { exact: true }).click();
    await expect(page.getByText(/Pausa del operador/).first()).toBeVisible();
    expect(errors).toEqual([]);
  } finally { stopWorker(worker); }
});
