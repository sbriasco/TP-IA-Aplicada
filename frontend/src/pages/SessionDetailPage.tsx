import { useEffect, useState } from "react";

import { API_BASE_URL } from "../api/config";
import { ApiRequestError } from "../api/http";
import { getSession, referenceFrameUrl } from "../api/sessions";
import { AppShell } from "../components/AppShell";
import { Link } from "../components/Link";
import { StartAnalysisSection } from "../components/StartAnalysisSection";
import { ScenePreview } from "../components/ScenePreview";
import { VideoRelinkForm } from "../components/VideoRelinkForm";
import type { SessionDetail, VideoAvailability, VideoSource } from "../types/session";

import styles from "./SessionDetailPage.module.css";

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
    <dl className={styles.rows}>
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
  const [selectedConfigurationId, setSelectedConfigurationId] = useState("");

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
      <AppShell title="Sesión">
        {backLink}
        <p role="status">Cargando sesión…</p>
      </AppShell>
    );
  }
  if (state.kind === "error") {
    return (
      <AppShell title="Sesión">
        {backLink}
        <p role="alert">{state.message}</p>
      </AppShell>
    );
  }

  const { session } = state;
  const { video, reference_frame: frame } = session;

  return (
    <AppShell title={session.name} context="Detalle" sessionId={session.id} canEdit={session.reference_frame !== null}>
      {backLink}
      <p className={styles.description}>Definí qué espacios querés medir y elegí una configuración para analizar este video.</p>
      <div className={frame === null ? styles.detailsOnly : styles.layout}>
      <div className={styles.workspace}>

      {frame !== null && (
        <section className={styles.panel} aria-labelledby="frame-title">
          <div className={styles.frameHeading}>
            <div><h2 id="frame-title">Tu espacio</h2><p>Las zonas y líneas muestran qué medirá la configuración seleccionada.</p></div>
            <Link className={styles.editAction} href={`/sessions/${encodeURIComponent(session.id)}/editor`}>Editar escena</Link>
          </div>
          <div className={styles.frameSurface}>
          <ScenePreview
            apiBaseUrl={apiBaseUrl}
            versionId={selectedConfigurationId}
            frameUrl={referenceFrameUrl(apiBaseUrl, frame)}
            label={`Frame de referencia de ${session.name}`}
            width={frame.width}
            height={frame.height}
          />
          </div>
          <div className={styles.frameCaption}><span>Imagen de referencia · {formatSeconds(frame.video_timestamp_seconds)} del video</span><span>{session.camera.name} · {frame.width} × {frame.height}</span></div>
        </section>
      )}


      </div>
      <div className={styles.information}>
      {session.source_kind === "video_file" && <div className={styles.panel}>
        <StartAnalysisSection apiBaseUrl={apiBaseUrl} session={session} onConfigurationChange={setSelectedConfigurationId} />
      </div>}
      <section className={styles.panel} aria-label="Información de la sesión"><details className={styles.sessionInfo}><summary>Información de la sesión</summary>
      <dl className={styles.rows}>
        <dt>Cámara</dt>
        <dd>{session.camera.name}</dd>
        <dt>Tipo</dt>
        <dd>{session.source_kind === "video_file" ? "Video" : "Sintética"}</dd>
        <dt>Creada</dt>
        <dd>
          <time dateTime={session.created_at}>{new Date(session.created_at).toLocaleString()}</time>
        </dd>
      </dl>
      </details>
      </section>

      {video === null ? (
        <p>Esta sesión es sintética: no tiene video ni frame de referencia.</p>
      ) : (
        <>
          <section className={`${styles.panel} ${styles.videoPanel}`} aria-labelledby="video-title">
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
            {video.appears_incomplete && (
              <p role="status">
                {`El archivo parece incompleto: se leyeron ${video.frame_count} de ${video.declared_frame_count} frames declarados.`}
              </p>
            )}
            <details><summary>Detalles del archivo</summary><VideoMetadata video={video} /></details>
          </section>

          {session.duplicate_session_ids.length > 0 && (
            <section className={styles.panel} aria-labelledby="duplicates-title">
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
      </div>
      </div>
    </AppShell>
  );
}
