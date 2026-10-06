import { useEffect, useId, useRef, useState } from "react";
import { FileVideo, HardDrive, UploadCloud, X } from "lucide-react";

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
  onCancel?: () => void;
  onBusyChange?: (busy: boolean) => void;
}

export function VideoUploadForm({ apiBaseUrl, onRegistered, onCancel, onBusyChange }: VideoUploadFormProps) {
  const id = useId();
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [cameraId, setCameraId] = useState("");
  const [phase, setPhase] = useState<UploadPhase>({ kind: "idle" });
  const [error, setError] = useState<string | null>(null);
  const controller = useRef<AbortController | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  useEffect(() => () => controller.current?.abort(), []);

  const busy = phase.kind !== "idle";
  useEffect(() => { onBusyChange?.(busy); }, [busy, onBusyChange]);

  function selectFile(value: File | null) {
    setFile(value);
    setError(null);
  }
  function removeFile() {
    selectFile(null);
    if (input.current) input.current.value = "";
  }

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
    <form className={styles.form} onSubmit={(event) => void handleSubmit(event)} aria-label="Registro de video">
      <fieldset className={styles.fields} disabled={busy}>
        <div className={styles.fileColumn}>
        <div className={styles.sectionLabel}><span>01</span><label htmlFor={`${id}-file`}>Archivo de video</label></div>
        <div className={`${styles.fileArea}${dragging ? " " + styles.dragging : ""}`} role="group" aria-label="Soltar archivo de video"
          onDragOver={event => { event.preventDefault(); if (!busy) setDragging(true); }}
          onDragLeave={event => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragging(false); }}
          onDrop={event => { event.preventDefault(); setDragging(false); const dropped = event.dataTransfer.files[0]; if (!busy && dropped) selectFile(dropped); }}>
        <input
          ref={input}
          className={styles.fileInput}
          id={`${id}-file`}
          type="file"
          accept={VIDEO_ACCEPT}
          required={file === null}
          onChange={event => selectFile(event.target.files?.[0] ?? null)}
        />
        {file === null ? <label className={styles.dropTarget} htmlFor={`${id}-file`}>
          <span className={styles.uploadIcon}><UploadCloud size={34} strokeWidth={1.5} aria-hidden="true" /></span>
          <strong>Arrastrá tu archivo de video aquí<br />o hacé clic para explorar</strong>
          <small>MP4, MPEG, AVI, MOV o MKV</small>
        </label> : <div className={styles.selected}>
          <div className={styles.selectedFile}><span className={styles.videoIcon}><FileVideo size={27} aria-hidden="true" /></span><div><strong>{file.name}</strong><small>{file.size < 1024 * 1024 ? `${Math.max(1, Math.ceil(file.size / 1024))} KB` : `${(file.size / (1024 * 1024)).toLocaleString("es-AR", { maximumFractionDigits: 1 })} MB`}</small></div><button type="button" className={styles.removeFile} disabled={busy} onClick={removeFile} aria-label="Quitar archivo"><X size={16} aria-hidden="true" /><span className={styles.srOnly}>Quitar archivo</span></button></div>
          <button type="button" disabled={busy} onClick={() => input.current?.click()}>Cambiar archivo</button>
        </div>}
        </div>
        </div>
        <div className={styles.details}>
        <div className={styles.name}>
        <div className={styles.sectionLabel}><span>02</span><label htmlFor={`${id}-name`}>Nombre de la sesión</label></div>
        <input
          id={`${id}-name`}
          value={name}
          maxLength={120}
          required
          placeholder="Ej. Pasillo central - Mañana"
          onChange={(event) => setName(event.target.value)}
        />
        </div>
        <div className={styles.camera}>
        <div className={styles.sectionLabel}><span>03</span><h3>Asignación de cámara</h3></div>
        <CameraPicker apiBaseUrl={apiBaseUrl} value={cameraId} onChange={setCameraId} label="Cámara asignada" createLegend="O registrar nueva cámara" />
        </div>
        </div>
      </fieldset>

      <UploadProgress phase={phase} analyzingText="Analizando video…" />
      {error !== null && <p role="alert">{error}</p>}
      <div className={styles.footer}><p><HardDrive size={15} aria-hidden="true" />El video se guardará en el worker de procesamiento.</p><div className={styles.actions}>{onCancel && <button type="button" disabled={busy} onClick={onCancel}>Cancelar</button>}<button type="submit" disabled={busy || file === null || name.trim() === "" || cameraId === ""}>Registrar video</button></div></div>
    </form>
  );
}
