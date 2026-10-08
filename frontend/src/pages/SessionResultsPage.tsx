import { useEffect, useId, useState } from "react";
import { lazy, Suspense } from "react";

import { Camera, Layers, ChevronRight } from "lucide-react";
import { ScenePreview } from "../components/ScenePreview";

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
import { EmptyState } from "../components/results/EmptyState";
import { EventsTable } from "../components/results/EventsTable";
import { StatusBadge } from "../components/results/StatusBadge";
import { ZoneSelect } from "../components/results/ZoneSelect";
import { Modal } from "../components/Modal";
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
  const [eventsOpen, setEventsOpen] = useState(false);
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
  const zoneSelectId = useId();

  useEffect(() => {
    let active = true;
    setEventsOpen(false);
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

  const finishedBadly = row?.status === "failed" || row?.status === "cancelled";
  const inProgress = row?.status === "pending" || row?.status === "processing";
  const durationSeconds = session?.video?.duration_seconds ?? 0;
  const rangeEnd = toSeconds === 0 ? durationSeconds : toSeconds;
  const series = presenceSeries(events, fromSeconds, rangeEnd);

  const frame = session?.reference_frame;
  return (
    <AppShell viewport={row?.result_complete === true && row.scene_version_id !== null && !finishedBadly} hideContext mainClassName={styles.main} title={session?.name ?? "Resultados"} context="Resultados" sessionId={sessionId} canEdit={session?.reference_frame != null}>
      {error !== null && <p role="alert">{error}</p>}
      {session === null && error === null && <p role="status">Cargando resultados…</p>}
      {session !== null && (
        <div className={styles.summary}>
          <div className={styles.summaryStart}>
            <p><Camera size={15} aria-hidden="true" />{session.camera.name} · {session.video?.original_filename ?? "Sesión sintética"}</p>
            {row?.version_number != null && <span><Layers size={14} aria-hidden="true" />Zonas aplicadas: Versión {row.version_number}</span>}
          </div>
          {row !== null && <StatusBadge source="video" status={row.status} />}
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
      {row?.result_complete === true && row.scene_version_id === null && <p className={styles.notice}>Esta sesión no tiene indicadores comerciales: el análisis sintético valida el procesamiento y la previsualización. Registrá un video y configurá su escena para consultar métricas por zona.</p>}
      {row?.result_complete === true && row.scene_version_id !== null && !finishedBadly && (
        <div className={styles.resultsWorkspace}>
        <div className={styles.analytics}>
          <section className={styles.overview} aria-label="Indicadores de la sesión">
            <div className={styles.sectionHeading}>
              <div className={styles.headingTitle}>
                <h2>Indicadores de la zona</h2>
                {metrics !== null && (
                  <span className={styles.trafficLine}>
                    Tráfico: {metrics.metrics.find(({ code }) => code === "traffic_total")?.value ?? 0}
                  </span>
                )}
              </div>
              {shops.length > 0 && <ZoneSelect id={zoneSelectId} className={styles.shop} value={shopId ?? ""} options={shops.map((shop) => ({ id: shop.shop_id, name: shop.name }))} onChange={setShopId} />}
            </div>
            {metrics === null ? <p role="status">Cargando indicadores…</p> : <>
              <ul className={`${styles.metrics} grid grid-cols-2 lg:grid-cols-4 gap-4`}>{metrics.metrics.filter((metric) => PRIMARY_CODES.has(metric.code)).map((metric) => <MetricCard key={metric.code} metric={metric} prominent />)}</ul>
              <details className={styles.moreMetrics}><summary>Ver todos los indicadores</summary><ul className={styles.metrics}>{metrics.metrics.filter((metric) => !PRIMARY_CODES.has(metric.code)).map((metric) => <MetricCard key={metric.code} metric={metric} prominent />)}</ul></details>
            </>}
          </section>
          <div className={styles.analysisGrid}>
            <section className={`${styles.panel} ${styles.flowPanel}`} aria-labelledby="flow-title">
              <h2 id="flow-title">Flujo temporal</h2>
              <p className={styles.description}>Tracks en el área externa en cada segundo. Sube al entrar y baja al salir.</p>
              <Suspense fallback={<p role="status">Cargando gráfico…</p>}><FlowChart fit points={series} fromSeconds={fromSeconds} toSeconds={rangeEnd} /></Suspense>
              <section className={styles.chartFooter} aria-label="Tramo temporal">
                {metrics !== null && <p className={styles.peak}>{peakCaption(metrics.peak.start_seconds, metrics.peak.track_count, durationSeconds)}</p>}
              <VideoTimeRange
                durationSeconds={durationSeconds}
                fromSeconds={fromSeconds}
                toSeconds={rangeEnd}
                onFromChange={setFromSeconds}
                onToChange={setToSeconds}
              />
                <details className={styles.filterHelp}><summary>Alcance del tramo</summary><p className={styles.filterNote}>El tramo recorta el gráfico y los hechos. Los indicadores corresponden a toda la sesión. Si se pierde el seguimiento, ese track deja de contar.</p></details>
              </section>

            </section>
            <div className={styles.sceneColumn}>
            <section className={`${styles.panel} ${styles.scenePanel}`} aria-labelledby="scene-title">
              <h2 id="scene-title">Distribución en la escena</h2>
              <p className={styles.description}>Zonas aplicadas sobre el frame de referencia.</p>
              {frame != null ? <figure className={styles.frame}>
                <div className={styles.frameViewport}><div className={styles.frameImage} style={{ aspectRatio: `${frame.width} / ${frame.height}`, width: `min(100%, ${frame.width / frame.height * 100}cqh)` }}>
                  <ScenePreview apiBaseUrl={apiBaseUrl} versionId={row.scene_version_id} frameUrl={referenceFrameUrl(apiBaseUrl, frame)} width={frame.width} height={frame.height} label="Frame de referencia con zonas aplicadas" showConfigurationBadge={false} />
                  {positions?.availability === "available" && positions.samples.length > 0 && <PositionHeatmap availability={positions.availability} samples={positions.samples} />}
                </div></div>
                {positions?.availability === "available" && positions.samples.length > 0 && <figcaption>Mapa de calor · posiciones observadas, no personas únicas</figcaption>}
              </figure> : <p className={styles.description}>Esta sesión no tiene frame de referencia.</p>}
            </section>
          <button type="button" className={styles.eventPanel} aria-haspopup="dialog" onClick={() => setEventsOpen(true)}>
            <span id="events-title">Hechos del análisis <span className={styles.count}>{events.length} hechos</span></span>
            <ChevronRight size={16} aria-hidden="true" />
          </button>
            </div>

          </div>
        </div>
          <SessionChatPanel key={sessionId} apiBaseUrl={apiBaseUrl} sessionId={sessionId} shopId={shopId} shopName={shops.find((shop) => shop.shop_id === shopId)?.name} />
        </div>
      )}
      {eventsOpen && <Modal wide title="Hechos del análisis" subtitle={`${events.length} hechos · zona seleccionada · ${fromSeconds}–${rangeEnd} s`} onClose={() => setEventsOpen(false)}>
        {events.length === 0 ? <EmptyState title="Sin hechos en este tramo">No hay hechos registrados para la zona y el tramo elegidos.</EmptyState> : <EventsTable label="Hechos del análisis">
            <thead><tr><th scope="col">Evento</th><th scope="col">Track</th><th scope="col">Tiempo del video</th></tr></thead>
            <tbody>{events.map((event, index) => <tr key={`${event.track_id}-${event.kind}-${event.video_timestamp_seconds}-${index}`}>
              <td>{EVENT_NAME[event.kind] ?? "Evento registrado"}</td><td className={styles.track}>Track {event.track_id}</td><td>{event.video_timestamp_seconds} s</td>
            </tr>)}</tbody>
          </EventsTable>}
      </Modal>}
    </AppShell>
  );
}
