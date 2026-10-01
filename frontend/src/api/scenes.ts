import type {
  AnalysisJob,
  AspectRatios,
  CreateSceneVersionResult,
  SceneIssue,
  SceneVersion,
  SceneVersionCreate,
  SceneVersionSummary,
} from "../types/scene";
import type { ApiError } from "../types/session";
import { ApiRequestError, requestJson } from "./http";

const JSON_HEADERS = { "Content-Type": "application/json" };

/** Versiones de la cámara, la más nueva primero. */
export function listSceneVersions(
  apiBaseUrl: string,
  cameraId: string,
): Promise<SceneVersionSummary[]> {
  return requestJson<SceneVersionSummary[]>(
    `${apiBaseUrl}/cameras/${encodeURIComponent(cameraId)}/scene-versions`,
  );
}

export function getSceneVersion(apiBaseUrl: string, sceneVersionId: string): Promise<SceneVersion> {
  return requestJson<SceneVersion>(
    `${apiBaseUrl}/scene-versions/${encodeURIComponent(sceneVersionId)}`,
  );
}

export async function deleteSceneVersion(apiBaseUrl: string, sceneVersionId: string): Promise<void> {
  await requestJson<unknown>(`${apiBaseUrl}/scene-versions/${encodeURIComponent(sceneVersionId)}`, { method: "DELETE" });
}

/**
 * Guarda una versión nueva. Un 422 `invalid_scene_configuration` no se lanza: devuelve
 * `{ok: false, errors}` con todos los problemas. Cualquier otro error se lanza como `ApiRequestError`.
 */
export async function createSceneVersion(
  apiBaseUrl: string,
  cameraId: string,
  payload: SceneVersionCreate,
): Promise<CreateSceneVersionResult> {
  try {
    const { warnings, ...version } = await requestJson<SceneVersion & { warnings: SceneIssue[] }>(
      `${apiBaseUrl}/cameras/${encodeURIComponent(cameraId)}/scene-versions`,
      { method: "POST", headers: JSON_HEADERS, body: JSON.stringify(payload) },
    );
    return { ok: true, version, warnings };
  } catch (error) {
    if (error instanceof ApiRequestError && error.error.code === "invalid_scene_configuration") {
      const errors = error.error.extra.errors;
      if (Array.isArray(errors)) {
        return { ok: false, errors: errors as SceneIssue[] };
      }
    }
    throw error;
  }
}

export function createVideoAnalysisJob(
  apiBaseUrl: string,
  sessionId: string,
  sceneVersionId: string,
): Promise<AnalysisJob> {
  return requestJson<AnalysisJob>(`${apiBaseUrl}/sessions/${encodeURIComponent(sessionId)}/jobs`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ kind: "video_analysis", scene_version_id: sceneVersionId }),
  });
}

/** Ratios de un `aspect_ratio_mismatch`; `null` si el error es otro o no los trae. */
export function aspectRatioMismatch(error: ApiError): AspectRatios | null {
  const { video_aspect_ratio: video, version_aspect_ratio: version } = error.extra;
  if (error.code !== "aspect_ratio_mismatch" || typeof video !== "number" || typeof version !== "number") {
    return null;
  }
  return { video, version };
}
