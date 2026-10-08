import { useEffect, useId, useRef, useState } from "react";

import { AlertTriangle, UploadCloud } from "lucide-react";
import styles from "./VideoRelinkForm.module.css";

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
  compact?: boolean;
  availabilityText?: string;
  apiBaseUrl: string;
  sessionId: string;
  onRelinked: (session: SessionDetail) => void;
}

export function VideoRelinkForm({ apiBaseUrl, sessionId, onRelinked, compact = false, availabilityText }: VideoRelinkFormProps) {
  const id = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [phase, setPhase] = useState<UploadPhase>({ kind: "idle" });
  const [error, setError] = useState<string | null>(null);
  const controller = useRef<AbortController | null>(null);

  useEffect(() => () => controller.current?.abort(), []);

  const busy = phase.kind !== "idle";

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await upload(file);
  }

  async function upload(selected: File | null) {
    if (busy || selected === null) return;
    setError(null);
    if (!(await canReadFile(selected))) {
      setError("No se pudo leer el archivo elegido.");
      return;
    }

    controller.current = new AbortController();
    setPhase({ kind: "uploading", loaded: 0, total: selected.size });
    try {
      const session = await relinkVideo(apiBaseUrl, sessionId, selected, {
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

  if (compact) return <div>
    <div className={styles.banner}>
      <AlertTriangle size={16} aria-hidden="true" />
      <span>{availabilityText ?? "Archivo no encontrado en el almacenamiento local."}</span>
      <button type="button" disabled={busy} onClick={() => inputRef.current?.click()}><UploadCloud size={14} aria-hidden="true" />{busy ? "Re-vinculando…" : "Re-vincular video"}</button>
    </div>
    <input ref={inputRef} hidden id={`${id}-file`} aria-label="Archivo de video" type="file" accept={VIDEO_ACCEPT} disabled={busy}
      onChange={event => { const chosen = event.target.files?.[0] ?? null; event.target.value = ""; void upload(chosen); }} />
    <UploadProgress phase={phase} analyzingText="Verificando el video…" />
    {error !== null && <p role="alert">{error}</p>}
    {error !== null && <button type="button" disabled={busy} onClick={() => inputRef.current?.click()}>Elegir otro archivo</button>}
  </div>;

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
