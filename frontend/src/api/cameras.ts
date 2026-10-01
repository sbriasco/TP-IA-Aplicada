import type { Camera } from "../types/session";
import { ApiRequestError, requestJson } from "./http";

export interface CreateCameraResult {
  camera: Camera;
  /** `true` si ya existía una cámara con ese nombre (`camera_exists`). */
  existed: boolean;
}

export function listCameras(apiBaseUrl: string): Promise<Camera[]> {
  return requestJson<Camera[]>(`${apiBaseUrl}/cameras`);
}

export function renameCamera(apiBaseUrl: string, cameraId: string, name: string): Promise<Camera> {
  return requestJson<Camera>(`${apiBaseUrl}/cameras/${encodeURIComponent(cameraId)}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }),
  });
}

export async function deleteCamera(apiBaseUrl: string, cameraId: string): Promise<void> {
  await requestJson<unknown>(`${apiBaseUrl}/cameras/${encodeURIComponent(cameraId)}`, { method: "DELETE" });
}

export async function createCamera(apiBaseUrl: string, name: string): Promise<CreateCameraResult> {
  try {
    const camera = await requestJson<Camera>(`${apiBaseUrl}/cameras`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    return { camera, existed: false };
  } catch (error) {
    if (error instanceof ApiRequestError && error.error.code === "camera_exists") {
      const existing = error.error.extra.existing_camera as Camera | undefined;
      if (existing !== undefined) {
        return { camera: existing, existed: true };
      }
    }
    throw error;
  }
}
