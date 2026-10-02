import { useEffect, useState } from "react";
import { lazy, Suspense } from "react";

import { API_BASE_URL } from "../api/config";
import { ApiRequestError } from "../api/http";
import {
  getJobMeasures,
  getPositionSamples,
  getSceneShops,
  getSessionEvents,
  getShopMetrics,
  type AnalysisMeasure,
  type PositionSamples,
  type SceneEvent,
  type SceneShop,
  type ShopMetrics,
} from "../api/metrics";
import { listProcessedSessions, type ProcessedSession } from "../api/processedSessions";
import { getSession, referenceFrameUrl } from "../api/sessions";
import { AppShell } from "../components/AppShell";
import { PositionHeatmap } from "../components/PositionHeatmap";
import { SessionChatPanel } from "../components/SessionChatPanel";
import { Link } from "../components/Link";
import { MetricCard } from "../components/MetricCard";
import { VideoTimeRange } from "../components/VideoTimeRange";
import { presenceSeries } from "../flow/presenceSeries";
import { EVENT_NAME, METRIC_NAME, peakCaption } from "../presentation/metrics";
import type { SessionDetail } from "../types/session";

import styles from "./SessionResultsPage.module.css";

const PARTIAL_CODES = new Set(["entries", "exits", "visible_occupancy"]);
const PRIMARY_CODES = new Set(["traffic_total", "entries", "entry_rate", "dwell_mean_seconds"]);
const FlowChart = lazy(() => import("../components/FlowChart").then((module) => ({ default: module.FlowChart })));

interface SessionResultsPageProps {
  sessionId: string;
  apiBaseUrl?: string;
}

export function SessionResultsPage({
  sessionId,
  apiBaseUrl = API_BASE_URL,
}: SessionResultsPageProps) {
  const [row, setRow] = useState<ProcessedSession | null>(null);
  const [session, setSession] = useState<SessionDetail | null>(null);
  const [shops, setShops] = useState<SceneShop[]>([]);
  const [shopId, setShopId] = useState<string | null>(null);
  const [fromSeconds, setFromSeconds] = useState(0);
  const [toSeconds, setToSeconds] = useState(0);
  const [metrics, setMetrics] = useState<ShopMetrics | null>(null);
  const [events, setEvents] = useState<SceneEvent[]>([]);
  const [measures, setMeasures] = useState<AnalysisMeasure[]>([]);
  const [positions, setPositions] = useState<PositionSamples | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([listProcessedSessions(apiBaseUrl), getSession(apiBaseUrl, sessionId)])
      .then(([rows, detail]) => {
        if (!active) return;
        const match = rows.find((item) => item.session_id === sessionId) ?? null;
        setRow(match);
        setSession(detail);
        setToSeconds(detail.video?.duration_seconds ?? 0);
        if (match?.status === "pending" || match?.status === "processing") {
          return getJobMeasures(apiBaseUrl, match.job_id).then((partials) => {
            if (active) setMeasures(partials);
          });
        }
        if (match?.result_complete && match.scene_version_id !== null) {
          return getSceneShops(apiBaseUrl, match.scene_version_id).then((sceneShops) => {
            if (!active) return;
            setShops(sceneShops);
            setShopId(sceneShops[0]?.shop_id ?? null);
          });
        }
        return undefined;
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(reason instanceof ApiRequestError ? reason.error.message : "Ocurrió un error inesperado.");
        }
      });
    return () => {
      active = false;
    };
  }, [apiBaseUrl, sessionId]);

  useEffect(() => {
    if (row?.result_complete !== true || shopId === null) return;
    let active = true;
    setMetrics(null);
    getShopMetrics(apiBaseUrl, sessionId, shopId)
      .then((result) => {
        if (active) setMetrics(result);
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(reason instanceof ApiRequestError ? reason.error.message : "Ocurrió un error inesperado.");
        }
      });
    return () => {
      active = false;
    };
  }, [apiBaseUrl, sessionId, shopId, row?.result_complete]);

  useEffect(() => {
    if (row?.result_complete !== true || shopId === null) return;
    let active = true;
    setEvents([]);
    getSessionEvents(apiBaseUrl, sessionId, shopId, fromSeconds, toSeconds)
      .then((result) => {
        if (active) setEvents(result);
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(reason instanceof ApiRequestError ? reason.error.message : "Ocurrió un error inesperado.");
        }
      });
    return () => {
      active = false;
    };
  }, [apiBaseUrl, sessionId, shopId, fromSeconds, toSeconds, row?.result_complete]);

  useEffect(() => {
    if (row?.result_complete !== true) return;
    let active = true;
    getPositionSamples(apiBaseUrl, row.job_id)
      .then((result) => {
        if (active) setPositions(result);
      })
      .catch(() => {
        if (active) setPositions({ job_id: row.job_id, availability: "unavailable", samples: [] });
      });
    return () => {
      active = false;
    };
  }, [apiBaseUrl, row?.job_id, row?.result_complete]);

  const videoMissing =
    session?.video?.availability === "missing" || session?.video?.availability === "mismatch";
  const finishedBadly = row?.status === "failed" || row?.status === "cancelled";
  const inProgress = row?.status === "pending" || row?.status === "processing";
  const durationSeconds = session?.video?.duration_seconds ?? 0;
  const rangeEnd = toSeconds === 0 ? durationSeconds : toSeconds;
  const series = presenceSeries(events, fromSeconds, rangeEnd);

  const frame = session?.reference_frame;
  return (
    <AppShell title={session?.name ?? "Resultados"} context="Resultados" sessionId={sessionId} canEdit={session?.reference_frame != null}>
      {error !== null && <p role="alert">{error}</p>}
      {session === null && error === null && <p role="status">Cargando resultados…</p>}
      {videoMissing && <p className={styles.notice}>El archivo no está en este equipo.</p>}
      {session !== null && (
        <div className={styles.summary}>
          <p>{session.camera.name} · {session.video?.original_filename ?? "Sesión sintética"}</p>
          {row?.version_number != null && <span>Escena · versión {row.version_number}</span>}
        </div>
      )}
      {session !== null && row === null && error === null && <p className={styles.notice}>Esta sesión todavía no tiene un análisis. Configurá la escena e iniciá el procesamiento desde el detalle.</p>}
      {finishedBadly && <p role="alert">El resultado quedó incompleto. {row?.failure_message ?? row?.failure_code}</p>}
      {inProgress && (
        <section className={styles.panel} aria-label="Resultados parciales">
          <h2>Análisis en curso</h2>
          <p>Estos valores son parciales y pueden cambiar hasta que termine el procesamiento.</p>
          <ul>{measures.filter((measure) => PARTIAL_CODES.has(measure.code)).map((measure) => (
            <li key={`${measure.shop_id}-${measure.code}`}>
              {measure.shop_name} · {METRIC_NAME[measure.code] ?? measure.code}: {measure.value ?? "no disponible"} <span className={styles.partial}>parcial</span>
            </li>
          ))}</ul>
          {row !== null && <Link href={`/?job=${encodeURIComponent(row.job_id)}`}>Ver avance del análisis →</Link>}
        </section>
      )}
      {row?.result_complete === true && row.scene_version_id === null && <p className={styles.notice}>Esta sesión no tiene indicadores comerciales: el análisis sintético valida el procesamiento y la previsualización. Registrá un video y configurá su escena para consultar métricas por local.</p>}
      {row?.result_complete === true && row.scene_version_id !== null && !finishedBadly && (
        <div className={styles.resultsWorkspace}>
        <div className={styles.analytics}>
          <section className={styles.overview} aria-label="Indicadores de la sesión">
            <div className={styles.sectionHeading}>
              <div><h2>Indicadores del local</h2><p>Valores de toda la sesión. El tramo seleccionado no cambia estas cifras.</p></div>
              {shops.length > 0 && <label className={styles.shop}>Local
                <select aria-label="Local" value={shopId ?? ""} onChange={(event) => setShopId(event.target.value)}>
                  {shops.map((shop) => <option key={shop.shop_id} value={shop.shop_id}>{shop.name}</option>)}
                </select>
              </label>}
            </div>
            {metrics === null ? <p role="status">Cargando indicadores…</p> : <>
              <ul className={styles.metrics}>{metrics.metrics.filter((metric) => PRIMARY_CODES.has(metric.code)).map((metric) => <MetricCard key={metric.code} metric={metric} />)}</ul>
              <details className={styles.moreMetrics}><summary>Ver todos los indicadores</summary><ul className={styles.metrics}>{metrics.metrics.filter((metric) => !PRIMARY_CODES.has(metric.code)).map((metric) => <MetricCard key={metric.code} metric={metric} />)}</ul></details>
            </>}
          </section>
          <div className={styles.analysisGrid}>
            <section className={styles.panel} aria-labelledby="flow-title">
              <h2 id="flow-title">Flujo temporal</h2>
              <p className={styles.description}>Tracks en la zona frontal en cada segundo. Sube al entrar y baja al salir.</p>
              <VideoTimeRange
                durationSeconds={durationSeconds}
                fromSeconds={fromSeconds}
                toSeconds={rangeEnd}
                onFromChange={setFromSeconds}
                onToChange={setToSeconds}
              />
              <details className={styles.filterHelp}><summary>Alcance del tramo</summary><p className={styles.filterNote}>El tramo recorta este gráfico y los hechos. Si se pierde el seguimiento, esa persona no sigue contando. Los indicadores de arriba no cambian.</p></details>
              {metrics !== null && <p className={styles.peak}>{peakCaption(metrics.peak.start_seconds, metrics.peak.track_count, durationSeconds)} <span>· Toda la sesión</span></p>}
              <Suspense fallback={<p role="status">Cargando gráfico…</p>}><FlowChart points={series} fromSeconds={fromSeconds} toSeconds={rangeEnd} /></Suspense>
            </section>
            <section className={styles.panel} aria-labelledby="scene-title">
              <h2 id="scene-title">Distribución en la escena</h2>
              <p className={styles.description}>Muestra de posiciones de toda la sesión sobre el frame de referencia.</p>
              {frame != null ? <figure className={styles.frame}>
                <div className={styles.frameImage}>
                  <img src={referenceFrameUrl(apiBaseUrl, frame)} alt="Frame de referencia" />
                  {positions?.availability === "available" && positions.samples.length > 0 && <PositionHeatmap availability={positions.availability} samples={positions.samples} />}
                </div>
                <figcaption>{positions === null ? "Cargando muestra de posiciones…" : positions.availability === "unavailable" || positions.samples.length === 0 ? "No hay muestra de posiciones en este equipo." : "Mapa de calor · posiciones observadas, no personas únicas"}</figcaption>
              </figure> : <p className={styles.description}>Esta sesión no tiene frame de referencia.</p>}
            </section>
          </div>
          <details className={styles.eventPanel}>
            <summary id="events-title">Hechos del análisis <span className={styles.count}>{events.length} hechos</span></summary>
            <p className={styles.description}>Eventos del local dentro del tramo seleccionado.</p>
            {events.length === 0 && <p className={styles.description}>No hay hechos registrados en este tramo.</p>}
            <ul className={styles.events} aria-label="Hechos">{events.map((event, index) => (
              <li key={`${event.track_id}-${event.kind}-${event.video_timestamp_seconds}-${index}`}>
                <span>{EVENT_NAME[event.kind] ?? "Evento registrado"}</span>
                <span className={styles.track}>Track {event.track_id}</span>
                <span>{event.video_timestamp_seconds} s</span>
              </li>
            ))}</ul>
          </details>
        </div>
          <SessionChatPanel key={sessionId} apiBaseUrl={apiBaseUrl} sessionId={sessionId} shopId={shopId} shopName={shops.find((shop) => shop.shop_id === shopId)?.name} />
        </div>
      )}
    </AppShell>
  );
}
