import { useEffect, useState } from "react";

import {
  cancelJob,
  getJob,
  previewUrl,
  type JobState,
  type PreviewMessage,
  type TerminalMessage,
} from "../api/jobs";

interface JobPreviewPageProps {
  jobId: string;
  apiBaseUrl?: string;
}

export function JobPreviewPage({
  jobId,
  apiBaseUrl = "http://127.0.0.1:8000",
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
    <main>
      <h1>Supervisión del trabajo</h1>
      <p role="status">{connection}</p>
      <dl>
        <dt>Estado</dt>
        <dd>{job?.status ?? "desconocido"}</dd>
        <dt>Frame</dt>
        <dd>{preview?.frame_index ?? "sin previsualización"}</dd>
        <dt>Timestamp del video</dt>
        <dd>{preview === null ? "—" : `${preview.video_timestamp_seconds} s`}</dd>
        <dt>Avance</dt>
        <dd>{preview === null ? "—" : `${preview.progress_percent} %`}</dd>
      </dl>
      <p>Esta vista acompaña el análisis y no promete la velocidad del video.</p>
      {job?.status === "cancelled" && (
        <p>Análisis cancelado. El resultado quedó incompleto.</p>
      )}
      {job?.status === "failed" && <p>El análisis falló.</p>}
      {canCancel && (
        <button type="button" onClick={() => void onCancel()}>
          Cancelar análisis
        </button>
      )}
      {preview !== null && (
        <img
          alt={`Previsualización del frame ${preview.frame_index}`}
          src={`data:${preview.image_media_type};base64,${preview.image_base64}`}
          {...(preview.schema_version === "1" ? { width: 320, height: 180 } : {})}
        />
      )}
    </main>
  );
}
