import type { LiveCheck, LiveDevices, LiveJobCreated, LiveResults } from "../types/live";
import type { SessionDetail } from "../types/session";
import { requestJson } from "./http";

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function positiveNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value > 0;
}

export function getLiveDevices(base: string): Promise<LiveDevices> {
  return requestJson<LiveDevices>(`${base}/live/devices`);
}

export function prepareWebcam(base: string, input: { name: string; registered_camera_id: string;
  device_index: number; label_mode: "directions" | "access" }): Promise<SessionDetail> {
  return requestJson<SessionDetail>(`${base}/live/sessions`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(input),
  });
}

export async function checkWebcam(base: string, sessionId: string): Promise<LiveCheck> {
  const value = await requestJson<unknown>(`${base}/sessions/${encodeURIComponent(sessionId)}/live/check`, { method: "POST" });
  if (!record(value) || typeof value.check_token !== "string" || value.check_token.length > 128 ||
    !positiveNumber(value.expires_in_seconds) || value.expires_in_seconds > 60 ||
    !positiveNumber(value.width) || value.width > 1920 || !positiveNumber(value.height) || value.height > 1080 ||
    value.image_media_type !== "image/jpeg" || typeof value.image_base64 !== "string" ||
    value.image_base64.length > 1048576 || !/^[A-Za-z0-9+/]+={0,2}$/.test(value.image_base64) || typeof value.backend !== "string") {
    throw new Error("La comprobación de webcam no cumple el contrato.");
  }
  return value as unknown as LiveCheck;
}

export async function startWebcam(base: string, sessionId: string, sceneVersionId: string,
  checkToken: string): Promise<LiveJobCreated> {
  const value = await requestJson<unknown>(`${base}/sessions/${encodeURIComponent(sessionId)}/live/start`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scene_version_id: sceneVersionId, check_token: checkToken, frame_confirmed: true }),
  });
  if (!record(value) || typeof value.id !== "string" || value.kind !== "live_analysis" || value.status !== "pending") {
    throw new Error("El inicio de webcam no cumple el contrato.");
  }
  return { id: value.id, kind: "live_analysis", status: "pending" };
}

export async function getLiveResults(base: string, jobId: string, shopId?: string,
  bucketCursor?: number): Promise<LiveResults> {
  const query = new URLSearchParams();
  if (shopId) query.set("shop_id", shopId);
  if (bucketCursor !== undefined) query.set("bucket_cursor", String(bucketCursor));
  const value = await requestJson<unknown>(`${base}/jobs/${encodeURIComponent(jobId)}/live-results?${query}`);
  if (!record(value) || value.job_id !== jobId || value.source_kind !== "webcam" ||
    typeof value.session_id !== "string" || !Array.isArray(value.shops) || !Array.isArray(value.minutes) ||
    typeof value.revision !== "number" || !Number.isSafeInteger(value.revision) || value.revision < 0 ||
    !["pending", "processing", "completed", "failed", "cancelled"].includes(String(value.status))) {
    throw new Error("Los resultados no corresponden a este análisis en vivo.");
  }
  return value as unknown as LiveResults;
}

export async function stopWebcam(base: string, jobId: string): Promise<void> {
  await requestJson<unknown>(`${base}/jobs/${encodeURIComponent(jobId)}/live/stop`, { method: "POST" });
}

export async function retryWebcam(base: string, jobId: string): Promise<void> {
  await requestJson<unknown>(`${base}/jobs/${encodeURIComponent(jobId)}/live/retry`, { method: "POST" });
}

export async function resumeWebcam(base: string, jobId: string, checkToken: string): Promise<void> {
  await requestJson<unknown>(`${base}/jobs/${encodeURIComponent(jobId)}/live/confirm-resume`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ check_token: checkToken, frame_confirmed: true }),
  });
}
