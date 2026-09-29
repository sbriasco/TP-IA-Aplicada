import { useEffect, useId, useRef, useState } from "react";

import { relinkVideo } from "../api/sessions";
import type { SessionDetail } from "../types/session";
import {
  VIDEO_ACCEPT,
  canReadFile,
  isAbort,
  UploadProgress,
  uploadErrorMessage,
  type UploadPhase,
} from "./UploadProgress";

interface VideoRelinkFormProps {
  apiBaseUrl: string;
  sessionId: string;
  onRelinked: (session: SessionDetail) => void;
}

export function VideoRelinkForm({ apiBaseUrl, sessionId, onRelinked }: VideoRelinkFormProps) {
  const id = useId();
  const [file, setFile] = useState<File | null>(null);
  const [phase, setPhase] = useState<UploadPhase>({ kind: "idle" });
  const [error, setError] = useState<string | null>(null);
  const controller = useRef<AbortController | null>(null);

  useEffect(() => () => controller.current?.abort(), []);

  const busy = phase.kind !== "idle";

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || file === null) return;
    setError(null);
    if (!(await canReadFile(file))) {
      setError("No se pudo leer el archivo elegido.");
      return;
    }

    controller.current = new AbortController();
    setPhase({ kind: "uploading", loaded: 0, total: file.size });
    try {
      const session = await relinkVideo(apiBaseUrl, sessionId, file, {
        signal: controller.current.signal,
        onUploadProgress: (loaded, total) => setPhase({ kind: "uploading", loaded, total }),
        onUploadComplete: () => setPhase({ kind: "analyzing" }),
      });
      setPhase({ kind: "idle" });
      onRelinked(session);
    } catch (reason) {
      if (isAbort(reason)) return;
      setError(uploadErrorMessage(reason));
      setPhase({ kind: "idle" });
    }
  }

  return (
    <form onSubmit={(event) => void handleSubmit(event)} aria-labelledby={`${id}-title`}>
      <h3 id={`${id}-title`}>Volver a cargar el video</h3>
      <p>Elegí el mismo archivo que se registró originalmente.</p>
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
        <button type="submit">Volver a cargar</button>
      </fieldset>
      <UploadProgress phase={phase} analyzingText="Verificando el video…" />
      {error !== null && <p role="alert">{error}</p>}
    </form>
  );
}
