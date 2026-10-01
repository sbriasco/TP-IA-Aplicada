import { useEffect, useId, useRef, useState } from "react";

import { registerVideoSession } from "../api/sessions";
import type { SessionDetail } from "../types/session";
import { CameraPicker } from "./CameraPicker";
import styles from "./VideoUploadForm.module.css";
import {
  VIDEO_ACCEPT,
  canReadFile,
  isAbort,
  UploadProgress,
  uploadErrorMessage,
  type UploadPhase,
} from "./UploadProgress";

interface VideoUploadFormProps {
  apiBaseUrl: string;
  onRegistered: (session: SessionDetail) => void;
}

export function VideoUploadForm({ apiBaseUrl, onRegistered }: VideoUploadFormProps) {
  const id = useId();
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [cameraId, setCameraId] = useState("");
  const [phase, setPhase] = useState<UploadPhase>({ kind: "idle" });
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
      setError(uploadErrorMessage(reason));
      setPhase({ kind: "idle" });
    }
  }

  return (
    <form className={styles.form} onSubmit={(event) => void handleSubmit(event)} aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`}>Registrar video</h2>
      <p className={styles.description}>Empezá con un video de cámara fija. Podrás dibujar los locales y las zonas en el siguiente paso.</p>
      <fieldset className={styles.fields} disabled={busy}>
        <div className={styles.file}>
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
        <small>MP4, MPEG, AVI, MOV o MKV · Cámara fija</small>
        </div>
        <div className={styles.name}>
        <label htmlFor={`${id}-name`}>Nombre de la sesión</label>
        <input
          id={`${id}-name`}
          value={name}
          maxLength={120}
          required
          placeholder="Por ejemplo, Pasillo central · Mañana"
          onChange={(event) => setName(event.target.value)}
        />
        </div>
        <CameraPicker apiBaseUrl={apiBaseUrl} value={cameraId} onChange={setCameraId} />
        <div className={styles.submit}><button type="submit">Registrar video</button><small>El video se guarda en el equipo de procesamiento.</small></div>
      </fieldset>

      <UploadProgress phase={phase} analyzingText="Analizando video…" />
      {error !== null && <p role="alert">{error}</p>}
    </form>
  );
}
