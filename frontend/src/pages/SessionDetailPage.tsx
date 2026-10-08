import { useEffect, useState } from "react";

import { Layers, ChevronDown } from "lucide-react";
import type { SceneVersionSummary } from "../types/scene";

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
import { LivePreparationPage } from "./LivePreparationPage";

const AVAILABILITY_TEXT: Record<VideoAvailability, string> = {
  available: "Video disponible en este equipo",
  missing: "Archivo no encontrado en el almacenamiento local.",
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
      <dt>Archivo original</dt>
      <dd>{video.original_filename}</dd>
    </dl>
  );
}

export function SessionDetailPage({ sessionId, apiBaseUrl = API_BASE_URL }: SessionDetailPageProps) {
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [notice, setNotice] = useState<string | null>(null);
  const [selectedVersion, setSelectedVersion] = useState<SceneVersionSummary | undefined>();
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
  if (session.source_kind === "webcam") {
    return <LivePreparationPage sessionId={session.id} apiBaseUrl={apiBaseUrl} />;
  }
  const { video, reference_frame: frame } = session;

  return (
    <AppShell title={session.name} context="Detalle" sessionId={session.id} canEdit={session.reference_frame !== null}>
      {backLink}

      <div className={frame === null ? styles.detailsOnly : `${styles.layout} grid grid-cols-1 lg:grid-cols-12 gap-6 items-start`}>
      <div className={`${styles.workspace} lg:col-span-7`}>

      {frame !== null && (
        <section className={styles.panel} aria-labelledby="frame-title">
          <div className={styles.frameHeading}>
            <div className={styles.previewTitle}><h2 id="frame-title">Escena y zonas configuradas</h2>{selectedVersion && <span className={styles.badge} aria-label="Configuración activa">Configuración {selectedVersion.version_number}</span>}</div>
            <Link className={styles.editAction} href={`/sessions/${encodeURIComponent(session.id)}/editor`}><Layers size={15} aria-hidden="true" />Editar en canvas</Link>
          </div>
          <div className={styles.frameSurface} style={{ aspectRatio: `${frame.width} / ${frame.height}` }}>
          <ScenePreview
            apiBaseUrl={apiBaseUrl}
            versionId={selectedConfigurationId}
            showConfigurationBadge={false}
            frameUrl={referenceFrameUrl(apiBaseUrl, frame)}
            label={`Frame de referencia de ${session.name}`}
            width={frame.width}
            height={frame.height}
          />
          </div>
          <div className={styles.frameCaption}><span>Frame {Math.floor(frame.video_timestamp_seconds / 60)}:{String(Math.floor(frame.video_timestamp_seconds % 60)).padStart(2, "0")} · Cámara: {session.camera.name} · {frame.width}x{frame.height}</span></div>
        </section>
      )}


      </div>
      <div className={`${styles.information} lg:col-span-5`}>
        <section className={`${styles.panel} ${styles.console}`} aria-label="Consola de inferencia">
          {video && (video.availability === "missing" || video.availability === "mismatch") && <VideoRelinkForm
            compact availabilityText={AVAILABILITY_TEXT[video.availability]} apiBaseUrl={apiBaseUrl} sessionId={session.id}
            onRelinked={updated => { setState({ kind: "loaded", session: updated }); setNotice("El video se volvió a cargar en este equipo."); }} />}
          {video?.availability === "not_configured" && <p role="alert" data-availability="not_configured">{AVAILABILITY_TEXT.not_configured}</p>}
          {notice !== null && <p role="status">{notice}</p>}
          {session.source_kind === "video_file" && <StartAnalysisSection apiBaseUrl={apiBaseUrl} session={session}
            onConfigurationChange={setSelectedConfigurationId} onVersionChange={setSelectedVersion} />}
          {video?.appears_incomplete && <p role="status">{`El archivo parece incompleto: se leyeron ${video.frame_count} de ${video.declared_frame_count} frames declarados.`}</p>}
          <details className={styles.sessionInfo} aria-label="Detalles del archivo y sesión">
            <summary>Detalles del archivo y sesión<ChevronDown size={16} aria-hidden="true" /></summary>
            <dl className={styles.rows}>
              <dt>Cámara</dt><dd>{session.camera.name}</dd>
              <dt>Tipo</dt><dd>{session.source_kind === "video_file" ? "Video" : "Sintética"}</dd>
              <dt>Creada</dt><dd><time dateTime={session.created_at}>{new Date(session.created_at).toLocaleString("es-AR")}</time></dd>
              {video && <><dt>Disponibilidad</dt><dd data-availability={video.availability}>{AVAILABILITY_TEXT[video.availability]}</dd></>}
            </dl>
            {video ? <VideoMetadata video={video} /> : <p>Esta sesión es sintética: no tiene video ni frame de referencia.</p>}
            {session.duplicate_session_ids.length > 0 && <div><h3>Video repetido</h3><ul>{session.duplicate_session_ids.map(id => <li key={id}><Link href={`/sessions/${encodeURIComponent(id)}`}>Sesión {id}</Link></li>)}</ul></div>}
          </details>
        </section>

      </div>
      </div>
    </AppShell>
  );
}
