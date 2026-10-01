import { useEffect, useState } from "react";
import { API_BASE_URL } from "../api/config";

import {
  cancelJob,
  getJob,
  previewUrl,
  type JobState,
  type PreviewMessage,
  type TerminalMessage,
} from "../api/jobs";
import { AppShell } from "../components/AppShell";
import { Split } from "../components/Split";
import { Link } from "../components/Link";
import styles from "./JobPreviewPage.module.css";

interface JobPreviewPageProps {
  jobId: string;
  apiBaseUrl?: string;
}

export function JobPreviewPage({
  jobId,
  apiBaseUrl = API_BASE_URL,
}: JobPreviewPageProps) {
  const [job, setJob] = useState<JobState | null>(null);
  const [preview, setPreview] = useState<PreviewMessage | null>(null);
  const [connection, setConnection] = useState("Consultando API…");

  useEffect(() => {
    let active = true;
    let socket: WebSocket | null = null;

    async function connect() {
      try {
        const current = await getJob(apiBaseUrl, jobId);
        if (!active) return;
        setJob(current);
        if (current.status === "failed") {
          setConnection("El análisis falló");
          return;
        }
        if (current.status === "completed" || current.status === "cancelled") {
          setConnection("Trabajo finalizado");
          return;
        }
        socket = new WebSocket(previewUrl(apiBaseUrl, jobId));
        socket.addEventListener("open", () => setConnection("Previsualización conectada"));
        socket.addEventListener("message", (event: MessageEvent<string>) => {
          const message = JSON.parse(event.data) as PreviewMessage | TerminalMessage;
          if (message.type === "preview.update") {
            if (message.schema_version !== "1" && message.schema_version !== "2") {
              return;
            }
            setPreview(message);
          } else {
            setJob((value) => (value === null ? value : { ...value, status: message.status }));
            setConnection("Trabajo finalizado");
          }
        });
        socket.addEventListener("close", () => {
          setConnection((value) =>
            value === "Trabajo finalizado" ? value : "Previsualización desconectada",
          );
        });
      } catch (error) {
        if (active) {
          setConnection(
            error instanceof Error && error.message === "job_not_found"
              ? "Trabajo inexistente"
              : "API no disponible",
          );
        }
      }
    }

    void connect();
    return () => {
      active = false;
      socket?.close();
    };
  }, [apiBaseUrl, jobId]);

  async function onCancel() {
    try {
      const updated = await cancelJob(apiBaseUrl, jobId);
      setJob(updated);
      setConnection(
        updated.status === "failed" ? "El análisis falló" : "Trabajo finalizado",
      );
    } catch {
      setConnection("API no disponible");
    }
  }

  const canCancel = job?.status === "pending" || job?.status === "processing";

  return (
    <AppShell title="Supervisión del trabajo" context="Procesamiento" sessionId={job?.session_id}>
      <p className={styles.description}>Seguí el avance y la previsualización del análisis. Los tiempos corresponden al video.</p>
      <Split
        main={
          <div className={styles.preview}>
          <div className={styles.previewHeading}><span>PREVISUALIZACIÓN</span><span>{preview === null ? "Sin frame" : `Frame ${preview.frame_index}`}</span></div>
          {preview !== null ? (
            <img
              alt={`Previsualización del frame ${preview.frame_index}`}
              src={`data:${preview.image_media_type};base64,${preview.image_base64}`}
              {...(preview.schema_version === "1" ? { width: 320, height: 180 } : {})}
            />
          ) : <div className={styles.placeholder}><span aria-hidden="true">▣</span><p>{job?.status === "completed" ? "El análisis terminó." : "La previsualización aparece al recibir frames del análisis."}</p></div>}
          </div>
        }
        side={
          <>
            <p role="status">{connection}</p>
            <h2>Estado del procesamiento</h2>
            <dl className={styles.rows}>
              <dt>Estado</dt>
              <dd>{job?.status ?? "desconocido"}</dd>
              <dt>Frame</dt>
              <dd>{preview?.frame_index ?? "sin previsualización"}</dd>
              <dt>Timestamp del video</dt>
              <dd>{preview === null ? "—" : `${preview.video_timestamp_seconds} s`}</dd>
              <dt>Avance</dt>
              <dd>{preview === null ? "—" : `${preview.progress_percent} %`}</dd>
            </dl>
            {preview !== null && <progress className={styles.progress} aria-label="Avance del análisis" value={preview.progress_percent} max={100} />}
            <p className={styles.note}>Esta vista acompaña el análisis y no promete la velocidad del video.</p>
            {job?.status === "cancelled" && <p>Análisis cancelado. El resultado quedó incompleto.</p>}
            {job?.status === "failed" && <p>El análisis falló.</p>}
            {canCancel && (
              <button className={styles.cancel} type="button" onClick={() => void onCancel()}>
                Cancelar análisis
              </button>
            )}
            {job?.status === "completed" && <Link className={styles.results} href={`/sessions/${encodeURIComponent(job.session_id)}/results`}>Ver resultados</Link>}
          </>
        }
      />
    </AppShell>
  );
}
