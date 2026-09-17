import { useEffect, useState } from "react";

import {
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
        if (current.status === "completed" || current.status === "failed") {
          setConnection("Trabajo finalizado");
          return;
        }
        socket = new WebSocket(previewUrl(apiBaseUrl, jobId));
        socket.addEventListener("open", () => setConnection("Previsualización conectada"));
        socket.addEventListener("message", (event: MessageEvent<string>) => {
          const message = JSON.parse(event.data) as PreviewMessage | TerminalMessage;
          if (message.type === "preview.update") {
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
      </dl>
      {preview !== null && (
        <img
          alt={`Previsualización del frame ${preview.frame_index}`}
          src={`data:${preview.image_media_type};base64,${preview.image_base64}`}
          width="320"
          height="180"
        />
      )}
    </main>
  );
}
