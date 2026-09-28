import { useEffect, useId, useRef, useState } from "react";

import { ApiRequestError } from "../api/http";
import { registerVideoSession } from "../api/sessions";
import type { SessionDetail } from "../types/session";
import { CameraPicker } from "./CameraPicker";

export const VIDEO_ACCEPT = ".mp4,.mpg,.mpeg,.avi,.mov,.mkv";

type Phase =
  | { kind: "idle" }
  | { kind: "uploading"; loaded: number; total: number }
  | { kind: "analyzing" };

interface VideoUploadFormProps {
  apiBaseUrl: string;
  onRegistered: (session: SessionDetail) => void;
}

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

function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

export function VideoUploadForm({ apiBaseUrl, onRegistered }: VideoUploadFormProps) {
  const id = useId();
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [cameraId, setCameraId] = useState("");
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const [error, setError] = useState<string | null>(null);
  const controller = useRef<AbortController | null>(null);

  useEffect(() => () => controller.current?.abort(), []);

  const busy = phase.kind !== "idle";

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || file === null || name.trim() === "" || cameraId === "") return;
    setError(null);
    if (!(await canReadFile(file))) {
      setError("No se pudo leer el archivo elegido.");
      return;
    }

    controller.current = new AbortController();
    setPhase({ kind: "uploading", loaded: 0, total: file.size });
    try {
      const session = await registerVideoSession(
        apiBaseUrl,
        { name: name.trim(), registeredCameraId: cameraId, file },
        {
          signal: controller.current.signal,
          onUploadProgress: (loaded, total) => setPhase({ kind: "uploading", loaded, total }),
          onUploadComplete: () => setPhase({ kind: "analyzing" }),
        },
      );
      onRegistered(session);
    } catch (reason) {
      if (isAbort(reason)) return;
      setError(
        reason instanceof ApiRequestError ? reason.error.message : "Ocurrió un error inesperado.",
      );
      setPhase({ kind: "idle" });
    }
  }

  return (
    <form onSubmit={(event) => void handleSubmit(event)} aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`}>Registrar video</h2>
      <fieldset disabled={busy}>
        <label htmlFor={`${id}-file`}>Archivo de video</label>
        <input
          id={`${id}-file`}
          type="file"
          accept={VIDEO_ACCEPT}
          required
          onChange={(event) => {
            setFile(event.target.files?.[0] ?? null);
            setError(null);
          }}
        />
        <label htmlFor={`${id}-name`}>Nombre de la sesión</label>
        <input
          id={`${id}-name`}
          value={name}
          maxLength={120}
          required
          onChange={(event) => setName(event.target.value)}
        />
        <CameraPicker apiBaseUrl={apiBaseUrl} value={cameraId} onChange={setCameraId} />
        <button type="submit">Registrar video</button>
      </fieldset>

      {phase.kind === "uploading" && (
        <p role="status">
          <label htmlFor={`${id}-progress`}>Subiendo video…</label>{" "}
          <progress id={`${id}-progress`} value={phase.loaded} max={phase.total || 1} />{" "}
          {phase.total > 0 ? Math.round((phase.loaded / phase.total) * 100) : 0} %
        </p>
      )}
      {phase.kind === "analyzing" && (
        <p role="status">
          <label htmlFor={`${id}-progress`}>Analizando video…</label>{" "}
          <progress id={`${id}-progress`} />
        </p>
      )}
      {error !== null && <p role="alert">{error}</p>}
    </form>
  );
}
