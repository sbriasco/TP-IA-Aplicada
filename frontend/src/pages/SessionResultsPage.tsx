import { useEffect, useState } from "react";
import { Bar, BarChart, XAxis, YAxis } from "recharts";

import { API_BASE_URL } from "../api/config";
import { ApiRequestError } from "../api/http";
import {
  getJobMeasures,
  getPositionSamples,
  getSceneShops,
  getSessionEvents,
  getShopMetrics,
  type AnalysisMeasure,
  type MetricValue,
  type PositionSamples,
  type SceneEvent,
  type SceneShop,
  type ShopMetrics,
} from "../api/metrics";
import { listProcessedSessions, type ProcessedSession } from "../api/processedSessions";
import { getSession, referenceFrameUrl } from "../api/sessions";
import { PositionHeatmap } from "../components/PositionHeatmap";
import { visibleBuckets } from "../flow/visibleBuckets";
import type { SessionDetail } from "../types/session";

import styles from "./SessionResultsPage.module.css";

const METRIC_NAME: Record<string, string> = {
  traffic_total: "Tráfico",
  store_pass: "Pasos",
  entries: "Entradas",
  exits: "Salidas",
  entry_rate: "Tasa de ingreso",
  dwell_mean_seconds: "Permanencia media",
  dwell_median_seconds: "Permanencia mediana",
  visible_occupancy: "Ocupación visible",
};

const PARTIAL_CODES = new Set(["entries", "exits", "visible_occupancy"]);

const LABEL_TEXT: Record<string, string> = {
  visit_estimate: "estimación de visitas",
  visible: "visible",
  observable: "observable",
};

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
  const minutes =
    metrics === null ? [] : visibleBuckets(metrics.flow, fromSeconds, toSeconds === 0 ? Number.POSITIVE_INFINITY : toSeconds);

  return (
    <main>
      <h1>Resultados</h1>
      <p>{sessionId}</p>
      {error !== null && <p role="alert">{error}</p>}
      {videoMissing && (
        <p>El archivo no está en este equipo.</p>
      )}
      {session?.reference_frame != null && (
        <figure className={styles.frame}>
          <img
            src={referenceFrameUrl(apiBaseUrl, session.reference_frame)}
            alt="Frame de referencia"
          />
          {positions !== null && (
            <PositionHeatmap availability={positions.availability} samples={positions.samples} />
          )}
        </figure>
      )}
      {finishedBadly && <p>{row?.failure_message ?? row?.failure_code}</p>}
      {inProgress && (
        <ul>
          {measures
            .filter((measure) => PARTIAL_CODES.has(measure.code))
            .map((measure) => (
              <li key={measure.code}>
                {METRIC_NAME[measure.code] ?? measure.code}: {measure.value ?? "no disponible"}{" "}
                <span className={styles.partial}>parcial</span>
              </li>
            ))}
        </ul>
      )}
      {row?.result_complete === true && !finishedBadly && (
        <>
          {shops.length > 0 && (
            <label>
              Local
              <select
                aria-label="Local"
                value={shopId ?? ""}
                onChange={(event) => setShopId(event.target.value)}
              >
                {shops.map((shop) => (
                  <option key={shop.shop_id} value={shop.shop_id}>
                    {shop.name}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label>
            Desde
            <input
              aria-label="Desde"
              type="number"
              min={0}
              value={fromSeconds}
              onChange={(event) => setFromSeconds(Number(event.target.value))}
            />
          </label>
          <label>
            Hasta
            <input
              aria-label="Hasta"
              type="number"
              min={0}
              value={toSeconds}
              onChange={(event) => setToSeconds(Number(event.target.value))}
            />
          </label>
          <ul>
            {(metrics?.metrics ?? []).map((metric) => (
              <li key={metric.code}>
                <MetricFigure metric={metric} />
              </li>
            ))}
          </ul>
          {metrics !== null && (
            <p>
              Horario pico: {metrics.peak.start_seconds} s, {metrics.peak.track_count}
            </p>
          )}
          <div className={styles.chart}>
            <BarChart width={480} height={240} data={minutes}>
              <XAxis dataKey="start_seconds" />
              <YAxis />
              <Bar dataKey="track_count" />
            </BarChart>
          </div>
          <ul aria-label="Hechos">
            {events.map((event) => (
              <li key={`${event.track_id}-${event.kind}-${event.video_timestamp_seconds}`}>
                {event.kind} {event.video_timestamp_seconds}
              </li>
            ))}
          </ul>
        </>
      )}
    </main>
  );
}

function MetricFigure({ metric }: { metric: MetricValue }) {
  const label = LABEL_TEXT[metric.label];
  if (metric.availability !== "available" || metric.value === null) {
    return (
      <>
        {METRIC_NAME[metric.code] ?? metric.code}: <span className={styles.unavailable}>no disponible</span>
        {metric.unavailable_reason ? ` (${metric.unavailable_reason})` : ""}
      </>
    );
  }
  return (
    <>
      {METRIC_NAME[metric.code] ?? metric.code}: {metric.value}
      {label !== undefined && <span className={styles.estimate}> {label}</span>}
    </>
  );
}
