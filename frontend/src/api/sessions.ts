import type { ReferenceFrame, SessionDetail, SessionSummary } from "../types/session";
import { ApiRequestError, NETWORK_ERROR, parseApiError, parseJson, requestJson } from "./http";

export interface UploadHandlers {
  /** Bytes enviados y total, desde `XMLHttpRequest.upload.onprogress`. */
  onUploadProgress?: (loaded: number, total: number) => void;
  /** El cuerpo terminó de enviarse; la API sigue analizando el video. */
  onUploadComplete?: () => void;
  signal?: AbortSignal;
}

export interface RegisterVideoSessionInput {
  name: string;
  registeredCameraId: string;
  file: File;
}

export function listSessions(
  apiBaseUrl: string,
  registeredCameraId?: string,
): Promise<SessionSummary[]> {
  const url = new URL(`${apiBaseUrl}/sessions`);
  if (registeredCameraId !== undefined) {
    url.searchParams.set("registered_camera_id", registeredCameraId);
  }
  return requestJson<SessionSummary[]>(url.toString());
}

export function getSession(apiBaseUrl: string, sessionId: string): Promise<SessionDetail> {
  return requestJson<SessionDetail>(`${apiBaseUrl}/sessions/${encodeURIComponent(sessionId)}`);
}

export function referenceFrameUrl(apiBaseUrl: string, frame: ReferenceFrame): string {
  return new URL(frame.url, apiBaseUrl).toString();
}

export function registerVideoSession(
  apiBaseUrl: string,
  { name, registeredCameraId, file }: RegisterVideoSessionInput,
  handlers: UploadHandlers = {},
): Promise<SessionDetail> {
  const url = new URL(`${apiBaseUrl}/video-sessions`);
  url.searchParams.set("name", name);
  url.searchParams.set("registered_camera_id", registeredCameraId);
  url.searchParams.set("filename", file.name);
  return sendFile("POST", url.toString(), file, handlers);
}

export function relinkVideo(
  apiBaseUrl: string,
  sessionId: string,
  file: File,
  handlers: UploadHandlers = {},
): Promise<SessionDetail> {
  const url = `${apiBaseUrl}/sessions/${encodeURIComponent(sessionId)}/video`;
  return sendFile("PUT", url, file, handlers);
}

// `fetch` no informa el progreso de subida, por eso se usa XMLHttpRequest.
function sendFile(
  method: "POST" | "PUT",
  url: string,
  file: Blob,
  { onUploadProgress, onUploadComplete, signal }: UploadHandlers,
): Promise<SessionDetail> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    const abort = () => request.abort();

    request.open(method, url);
    request.setRequestHeader("Content-Type", "application/octet-stream");
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        onUploadProgress?.(event.loaded, event.total);
      }
    };
    request.upload.onload = () => onUploadComplete?.();
    request.onload = () => {
      signal?.removeEventListener("abort", abort);
      const body = parseJson(request.responseText);
      if (request.status >= 200 && request.status < 300) {
        resolve(body as SessionDetail);
      } else {
        reject(new ApiRequestError(parseApiError(request.status, body)));
      }
    };
    request.onerror = () => {
      signal?.removeEventListener("abort", abort);
      reject(new ApiRequestError({ ...NETWORK_ERROR, extra: {} }));
    };
    request.onabort = () => {
      signal?.removeEventListener("abort", abort);
      reject(new DOMException("La subida fue cancelada.", "AbortError"));
    };

    if (signal?.aborted) {
      reject(new DOMException("La subida fue cancelada.", "AbortError"));
      return;
    }
    signal?.addEventListener("abort", abort);
    request.send(file);
  });
}
