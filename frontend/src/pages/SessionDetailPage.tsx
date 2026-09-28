import { useEffect, useState } from "react";

import { API_BASE_URL } from "../api/config";
import { ApiRequestError } from "../api/http";
import { getSession, referenceFrameUrl } from "../api/sessions";
import { Link } from "../components/Link";
import { VideoRelinkForm } from "../components/VideoRelinkForm";
import type { SessionDetail, VideoAvailability, VideoSource } from "../types/session";

const AVAILABILITY_TEXT: Record<VideoAvailability, string> = {
  available: "Video disponible en este equipo",
  missing: "Video no disponible en este equipo",
  mismatch: "El archivo de este equipo no coincide con el video registrado",
  not_configured: "Este equipo no tiene configurada la carpeta de videos (FLOWSIGHT_VIDEOS_DIR)",
};

interface SessionDetailPageProps {
  sessionId: string;
  apiBaseUrl?: string;
}

type LoadState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "loaded"; session: SessionDetail };

function formatSeconds(seconds: number): string {
  return `${seconds.toFixed(2)} s`;
}

function VideoMetadata({ video }: { video: VideoSource }) {
  return (
    <dl>
      <dt>Resolución</dt>
      <dd>
        {video.width} × {video.height}
      </dd>
      <dt>FPS</dt>
      <dd>
        {video.fps}
        {video.fps_is_estimated && " (estimado)"}
      </dd>
      <dt>Duración</dt>
      <dd>{formatSeconds(video.duration_seconds)}</dd>
      <dt>Frames</dt>
      <dd>{video.frame_count}</dd>
      <dt>Equipo de origen</dt>
      <dd>{video.origin_machine_id}</dd>
      <dt>SHA-256</dt>
      <dd>
        <code>{video.sha256}</code>
      </dd>
      <dt>Archivo original</dt>
      <dd>{video.original_filename}</dd>
    </dl>
  );
}

export function SessionDetailPage({ sessionId, apiBaseUrl = API_BASE_URL }: SessionDetailPageProps) {
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getSession(apiBaseUrl, sessionId)
      .then((session) => {
        if (active) setState({ kind: "loaded", session });
      })
      .catch((reason: unknown) => {
        if (!active) return;
        const message =
          reason instanceof ApiRequestError
            ? reason.error.code === "not_found"
              ? "Sesión inexistente."
              : reason.error.message
            : "Ocurrió un error inesperado.";
        setState({ kind: "error", message });
      });
    return () => {
      active = false;
    };
  }, [apiBaseUrl, sessionId]);

  const backLink = <Link href="/">Volver a las sesiones</Link>;

  if (state.kind === "loading") {
    return (
      <main>
        {backLink}
        <h1>Sesión</h1>
        <p role="status">Cargando sesión…</p>
      </main>
    );
  }
  if (state.kind === "error") {
    return (
      <main>
        {backLink}
        <h1>Sesión</h1>
        <p role="alert">{state.message}</p>
      </main>
    );
  }

  const { session } = state;
  const { video, reference_frame: frame } = session;

  return (
    <main>
      {backLink}
      <h1>{session.name}</h1>
      <dl>
        <dt>Cámara</dt>
        <dd>{session.camera.name}</dd>
        <dt>Tipo</dt>
        <dd>{session.source_kind === "video_file" ? "Video" : "Sintética"}</dd>
        <dt>Creada</dt>
        <dd>
          <time dateTime={session.created_at}>{new Date(session.created_at).toLocaleString()}</time>
        </dd>
      </dl>

      {video === null ? (
        <p>Esta sesión es sintética: no tiene video ni frame de referencia.</p>
      ) : (
        <>
          <section aria-labelledby="video-title">
            <h2 id="video-title">Video</h2>
            <p data-availability={video.availability}>{AVAILABILITY_TEXT[video.availability]}</p>
            {notice !== null && <p role="status">{notice}</p>}
            {(video.availability === "missing" || video.availability === "mismatch") && (
              <VideoRelinkForm
                apiBaseUrl={apiBaseUrl}
                sessionId={session.id}
                onRelinked={(updated) => {
                  setState({ kind: "loaded", session: updated });
                  setNotice("El video se volvió a cargar en este equipo.");
                }}
              />
            )}
            <VideoMetadata video={video} />
          </section>

          {session.duplicate_session_ids.length > 0 && (
            <section aria-labelledby="duplicates-title">
              <h2 id="duplicates-title">Video repetido</h2>
              <p>El mismo video también está registrado en estas sesiones:</p>
              <ul>
                {session.duplicate_session_ids.map((id) => (
                  <li key={id}>
                    <Link href={`/sessions/${encodeURIComponent(id)}`}>Sesión {id}</Link>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}

      {frame !== null && (
        <section aria-labelledby="frame-title">
          <h2 id="frame-title">Frame de referencia</h2>
          <p>
            Frame {frame.frame_index} ({formatSeconds(frame.video_timestamp_seconds)} del video)
          </p>
          <img
            src={referenceFrameUrl(apiBaseUrl, frame)}
            alt={`Frame de referencia de ${session.name}`}
            width={frame.width}
            height={frame.height}
            style={{ maxWidth: "100%", height: "auto" }}
          />
          <p>
            <Link href={`/sessions/${encodeURIComponent(session.id)}/editor`}>Editar escena</Link>
          </p>
        </section>
      )}
    </main>
  );
}
