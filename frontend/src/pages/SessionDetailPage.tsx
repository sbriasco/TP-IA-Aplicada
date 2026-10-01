import { useEffect, useState, type FormEvent } from "react";

import { API_BASE_URL } from "../api/config";
import { ApiRequestError } from "../api/http";
import { aspectRatioMismatch, createVideoAnalysisJob, listSceneVersions } from "../api/scenes";
import { getSession, referenceFrameUrl } from "../api/sessions";
import { AppShell } from "../components/AppShell";
import { Link } from "../components/Link";
import { VideoRelinkForm } from "../components/VideoRelinkForm";
import type { AnalysisJob, AspectRatios, SceneVersionSummary } from "../types/scene";
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

type VersionsState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "loaded"; versions: SceneVersionSummary[] };

type AnalysisOutcome =
  | { kind: "created"; job: AnalysisJob; version: SceneVersionSummary | undefined }
  | { kind: "scene_not_configured"; message: string }
  | { kind: "aspect_ratio_mismatch"; message: string; ratios: AspectRatios | null }
  | { kind: "error"; message: string };

function errorMessage(reason: unknown): string {
  return reason instanceof ApiRequestError ? reason.error.message : "Ocurrió un error inesperado.";
}

function formatRatio(ratio: number): string {
  return ratio.toFixed(3);
}

function versionLabel(version: SceneVersionSummary): string {
  const shops = version.shop_count === 1 ? "1 local" : `${version.shop_count} locales`;
  const created = new Date(version.created_at).toLocaleString();
  return `Versión ${version.version_number} · ${shops} · frame ${version.frame_width} × ${version.frame_height} · ${created}`;
}

/** Última versión por número, aunque la API ya las devuelve de la más nueva a la más vieja. */
function latestVersion(versions: SceneVersionSummary[]): SceneVersionSummary | undefined {
  return versions.reduce<SceneVersionSummary | undefined>(
    (latest, version) =>
      latest === undefined || version.version_number > latest.version_number ? version : latest,
    undefined,
  );
}

interface StartAnalysisSectionProps {
  apiBaseUrl: string;
  session: SessionDetail;
}

/** Compuerta de análisis (FR-025 a FR-028): elige una versión de escena y crea el trabajo. */
function StartAnalysisSection({ apiBaseUrl, session }: StartAnalysisSectionProps) {
  const cameraId = session.camera.id;
  const [versions, setVersions] = useState<VersionsState>({ kind: "loading" });
  const [selectedId, setSelectedId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [outcome, setOutcome] = useState<AnalysisOutcome | null>(null);

  useEffect(() => {
    let active = true;
    setVersions({ kind: "loading" });
    listSceneVersions(apiBaseUrl, cameraId)
      .then((loaded) => {
        if (!active) return;
        setVersions({ kind: "loaded", versions: loaded });
        setSelectedId(latestVersion(loaded)?.id ?? "");
      })
      .catch((reason: unknown) => {
        if (active) setVersions({ kind: "error", message: errorMessage(reason) });
      });
    return () => {
      active = false;
    };
  }, [apiBaseUrl, cameraId]);

  const editorHref = `/sessions/${encodeURIComponent(session.id)}/editor`;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (versions.kind !== "loaded" || selectedId === "") return;
    setSubmitting(true);
    setOutcome(null);
    try {
      const job = await createVideoAnalysisJob(apiBaseUrl, session.id, selectedId);
      const version = versions.versions.find((item) => item.id === job.scene_version_id);
      setOutcome({ kind: "created", job, version });
    } catch (reason) {
      if (reason instanceof ApiRequestError && reason.error.code === "scene_not_configured") {
        setOutcome({ kind: "scene_not_configured", message: reason.error.message });
      } else if (reason instanceof ApiRequestError && reason.error.code === "aspect_ratio_mismatch") {
        setOutcome({
          kind: "aspect_ratio_mismatch",
          message: reason.error.message,
          ratios: aspectRatioMismatch(reason.error),
        });
      } else {
        setOutcome({ kind: "error", message: errorMessage(reason) });
      }
    } finally {
      setSubmitting(false);
    }
  }

  let body;
  if (versions.kind === "loading") {
    body = <p role="status">Cargando versiones de escena…</p>;
  } else if (versions.kind === "error") {
    body = <p role="alert">{versions.message}</p>;
  } else if (versions.versions.length === 0) {
    body = (
      <p>
        La cámara {session.camera.name} no tiene ninguna configuración de escena. Creala antes de
        iniciar el análisis: <Link href={editorHref}>Abrir el editor de escena</Link>
      </p>
    );
  } else {
    const selectedVersion = versions.versions.find((item) => item.id === selectedId);
    body = (
      <form onSubmit={handleSubmit}>
        <label htmlFor="analysis-scene-version">Versión de escena</label>
        <select
          id="analysis-scene-version"
          value={selectedId}
          disabled={submitting}
          onChange={(event) => {
            setSelectedId(event.target.value);
            setOutcome(null);
          }}
        >
          {versions.versions.map((version) => (
            <option key={version.id} value={version.id}>
              {versionLabel(version)}
            </option>
          ))}
        </select>
        <button type="submit" disabled={submitting || selectedId === ""}>
          Iniciar análisis
        </button>
        {outcome?.kind === "created" && (
          <p role="status">
            Se creó el trabajo {outcome.job.id} en estado {outcome.job.status}
            {outcome.version !== undefined && ` con la versión ${outcome.version.version_number}`}.
            El worker lo procesará cuando esté disponible.{" "}
            <Link href={`/?job=${encodeURIComponent(outcome.job.id)}`}>Ver avance del análisis</Link>
          </p>
        )}
        {outcome?.kind === "scene_not_configured" && (
          <p role="alert">
            {outcome.message} <Link href={editorHref}>Abrir el editor de escena</Link>
          </p>
        )}
        {outcome?.kind === "aspect_ratio_mismatch" && (
          <p role="alert">
            {outcome.ratios !== null && selectedVersion !== undefined
              ? `La relación de aspecto del video (${formatRatio(outcome.ratios.video)}) difiere de la del frame de la versión ${selectedVersion.version_number} (${formatRatio(outcome.ratios.version)}). Creá una versión nueva sobre el frame de esta sesión.`
              : outcome.message}{" "}
            <Link href={editorHref}>Abrir el editor de escena</Link>
          </p>
        )}
        {outcome?.kind === "error" && <p role="alert">{outcome.message}</p>}
      </form>
    );
  }

  return (
    <section aria-labelledby="analysis-title">
      <h2 id="analysis-title">Iniciar análisis</h2>
      {body}
    </section>
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
      <p className={styles.description}>Revisá el video, configurá la escena y elegí la versión que usará el análisis.</p>
      <div className={styles.layout}>
      <div className={styles.information}>
      <section className={styles.panel} aria-label="Información de la sesión"><h2>Información de la sesión</h2>
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
      </section>

      {video === null ? (
        <p>Esta sesión es sintética: no tiene video ni frame de referencia.</p>
      ) : (
        <>
          <section className={styles.panel} aria-labelledby="video-title">
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
      <div className={styles.workspace}>

      {frame !== null && (
        <section className={styles.panel} aria-labelledby="frame-title">
          <h2 id="frame-title">Frame de referencia</h2>
          <p>
            Frame {frame.frame_index} ({formatSeconds(frame.video_timestamp_seconds)} del video)
          </p>
          <img
            className={styles.frame}
            src={referenceFrameUrl(apiBaseUrl, frame)}
            alt={`Frame de referencia de ${session.name}`}
            width={frame.width}
            height={frame.height}
          />
          <p>
            <Link href={`/sessions/${encodeURIComponent(session.id)}/editor`}>Editar escena</Link>
          </p>
        </section>
      )}

      {session.source_kind === "video_file" && <div className={styles.panel}>
        <StartAnalysisSection apiBaseUrl={apiBaseUrl} session={session} />
      </div>}
      </div>
      </div>
    </AppShell>
  );
}
