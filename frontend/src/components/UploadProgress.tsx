import { useId } from "react";

import { ApiRequestError } from "../api/http";

export const VIDEO_ACCEPT = ".mp4,.mpg,.mpeg,.avi,.mov,.mkv";

export type UploadPhase =
  | { kind: "idle" }
  | { kind: "uploading"; loaded: number; total: number }
  | { kind: "analyzing" };

/** Detecta en el navegador un archivo que ya no existe o no se puede leer (FR-003, FR-011). */
export function canReadFile(file: Blob): Promise<boolean> {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = () => resolve(true);
    reader.onerror = () => resolve(false);
    try {
      reader.readAsArrayBuffer(file.slice(0, 1));
    } catch {
      resolve(false);
    }
  });
}

export function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

export function uploadErrorMessage(error: unknown): string {
  return error instanceof ApiRequestError ? error.error.message : "Ocurrió un error inesperado.";
}

interface UploadProgressProps {
  phase: UploadPhase;
  analyzingText: string;
}

/** Barra determinada durante la subida e indeterminada mientras la API analiza el video. */
export function UploadProgress({ phase, analyzingText }: UploadProgressProps) {
  const id = useId();

  if (phase.kind === "uploading") {
    const percent = phase.total > 0 ? Math.round((phase.loaded / phase.total) * 100) : 0;
    return (
      <p role="status">
        <label htmlFor={id}>Subiendo video…</label>{" "}
        <progress id={id} value={phase.loaded} max={phase.total || 1} /> {percent} %
      </p>
    );
  }
  if (phase.kind === "analyzing") {
    return (
      <p role="status">
        <label htmlFor={id}>{analyzingText}</label> <progress id={id} />
      </p>
    );
  }
  return null;
}
