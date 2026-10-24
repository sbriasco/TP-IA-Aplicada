import { useEffect, useId, useState } from "react";
import { API_BASE_URL } from "../api/config";
import { requestJson } from "../api/http";
import { getLiveResults } from "../api/live";
import { AppShell } from "../components/AppShell";
import { CrossingChart } from "../components/CrossingChart";
import { Link } from "../components/Link";
import { PositionHeatmap } from "../components/PositionHeatmap";
import { Activity, ArrowLeft, ChevronDown, MapPinOff, VideoOff, AlertTriangle } from "lucide-react";
import { EmptyState } from "../components/results/EmptyState";
import { EventsTable } from "../components/results/EventsTable";
import { StatusBadge } from "../components/results/StatusBadge";
import { ZoneSelect } from "../components/results/ZoneSelect";
import type { LiveResults } from "../types/live";
import styles from "./LiveResultsPage.module.css";

interface LiveSamples { job_id: string; source_kind: "webcam"; time_basis: "capture";
  availability: "available" | "unavailable"; sample_count: number; returned_count: number;
  candidate_count: number; capacity: number; samples: { capture_timestamp_seconds: number; foot: [number, number] }[]; }
interface LiveEvents { events: { id: string; track_id: number; capture_timestamp_seconds: number;
  confirmed_at_capture_seconds: number; direction: "entry" | "exit" }[]; next_cursor: string | null; }

function visitNote(count: number | undefined) {
  if (count === undefined) return "Sin estadía calculada";
  if (count <= 0) return "Sin visitas con duración suficiente";
  return count + " visitas observadas";
}

export function LiveResultsPage({ jobId, apiBaseUrl = API_BASE_URL }: { jobId: string; apiBaseUrl?: string }) {
  const [result, setResult] = useState<LiveResults | null>(null);
  const [samples, setSamples] = useState<LiveSamples | null>(null);
  const [events, setEvents] = useState<LiveEvents | null>(null);
  const [shopId, setShopId] = useState<string | undefined>();
  const [error, setError] = useState<string | null>(null);
  const [sampleError, setSampleError] = useState<string | null>(null);
  const [eventError, setEventError] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const selectId = useId();
  useEffect(() => {
    let active = true; setError(null); setResult(null); setEvents(null); setEventError(null);
    void getLiveResults(apiBaseUrl, jobId, shopId).then((value) => {
      if (!active) return; setResult(value);
      const query = value.selected_shop_id ? `?shop_id=${encodeURIComponent(value.selected_shop_id)}` : "";
      void requestJson<LiveEvents>(`${apiBaseUrl}/jobs/${encodeURIComponent(jobId)}/live-events${query}`).then(
        (page) => { if (active) setEvents(page); }, () => { if (active) setEventError("No se pudieron cargar los cruces individuales."); });
    }, (cause: unknown) => { if (active) setError(cause instanceof Error ? cause.message : "No se pudieron cargar los resultados."); });
    return () => { active = false; };
  }, [apiBaseUrl, jobId, shopId]);
  useEffect(() => {
    let active = true; setSamples(null); setSampleError(null);
    void requestJson<LiveSamples>(`${apiBaseUrl}/jobs/${encodeURIComponent(jobId)}/position-samples`).then((value) => {
      if (value.job_id !== jobId || value.source_kind !== "webcam" || value.time_basis !== "capture" ||
        !Array.isArray(value.samples) || value.samples.length > 2000 || value.samples.some((sample) =>
          !Array.isArray(sample.foot) || sample.foot.length !== 2 || sample.foot.some((point) => !Number.isFinite(point) || point < 0 || point > 1))) {
        throw new Error("La muestra de posiciones no cumple el contrato.");
      }
      if (active) setSamples(value);
    }).catch(() => { if (active) setSampleError("No se pudo cargar la muestra de posiciones. Los cruces guardados siguen disponibles."); });
    return () => { active = false; };
  }, [apiBaseUrl, jobId]);
  async function moreMinutes() {
    if (!result || result.next_bucket_cursor === null || loadingMore) return;
    setLoadingMore(true);
    try {
      const page = await getLiveResults(apiBaseUrl, jobId, result.selected_shop_id ?? undefined, result.next_bucket_cursor);
      setResult((current) => current?.selected_shop_id === page.selected_shop_id ?
        { ...current, minutes: [...current.minutes, ...page.minutes], next_bucket_cursor: page.next_bucket_cursor } : current);
    } catch { setError("No se pudieron cargar más minutos."); }
    finally { setLoadingMore(false); }
  }
  async function moreEvents() {
    if (!result || !events?.next_cursor || loadingMore) return;
    const query = new URLSearchParams({ cursor: events.next_cursor });
    if (result.selected_shop_id) query.set("shop_id", result.selected_shop_id);
    setLoadingMore(true);
    try {
      const page = await requestJson<LiveEvents>(`${apiBaseUrl}/jobs/${encodeURIComponent(jobId)}/live-events?${query}`);
      setEvents((current) => current ? { events: [...current.events, ...page.events], next_cursor: page.next_cursor } : page);
    } catch { setEventError("No se pudieron cargar más cruces."); }
    finally { setLoadingMore(false); }
  }
  const summary = result?.summary;
  const access = summary?.label_mode === "access";
  const dwell = result?.zone_dwell?.[result.selected_shop_id ?? ""];
  const ended = result && ["completed", "failed", "cancelled"].includes(result.status);
  const captureDate = result?.capture_started_at;
  const dateLabel = captureDate && Number.isFinite(Date.parse(captureDate)) ? new Date(captureDate).toLocaleString("es-AR", {
    day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
    timeZone: "America/Argentina/Buenos_Aires",
  }) : "Fecha de inicio no disponible";
  const coverage = result && result.elapsed_capture_seconds > 0 ?
    (result.observed_seconds / result.elapsed_capture_seconds * 100).toLocaleString("es-AR", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + " %" : "--";
  const unanalyzed = result ? result.missing_seconds.toLocaleString("es-AR", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + " s sin analizar" : "";
  function duration(value: number | null | undefined) {
    if (value === undefined || value === null || value <= 0) return "--";
    return value < .1 ? "< 0,1 s" : value.toLocaleString("es-AR", { maximumFractionDigits: 1 }) + " s";
  }
  function minuteTime(seconds: number) {
    return captureDate && Number.isFinite(Date.parse(captureDate)) ? new Date(Date.parse(captureDate) + seconds * 1000)
      .toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: "America/Argentina/Buenos_Aires" }) : seconds.toFixed(0) + " s";
  }
  return <AppShell title="Reporte de análisis · Webcam en vivo" hideContext mainClassName={styles.main}
    pageHeader={<header className={styles.header}>
      <Link href="/" className={styles.back}><ArrowLeft size={15} aria-hidden="true" />Volver a mis análisis</Link>
      <div className={styles.titleRow}><h1>Reporte de análisis · Webcam en vivo</h1>
        {result && <time dateTime={captureDate ?? undefined}>{dateLabel}</time>}
      </div>
      {result && <div className={styles.badges}>
        <StatusBadge source="webcam" status={result.status} />
        {!result.coverage_complete && <span className={styles.warning} tabIndex={0}
          title={result.unknown_tail ? "Hay intervalos sin observaciones y un final desconocido; la duración corresponde al último checkpoint válido." : "Hubo pausas o interrupciones sin observaciones. Los intervalos sin cobertura no representan cero personas."}>
          <AlertTriangle size={14} aria-hidden="true" />Cobertura parcial ({result.observed_seconds.toFixed(1)}s / {result.elapsed_capture_seconds.toFixed(1)}s observados)
        </span>}
        <span className={styles.neutral}><VideoOff size={14} aria-hidden="true" />Sin grabación local</span>
        {!result.result_complete && <span className={styles.warning}>Resultados parciales</span>}
        {result.unknown_tail && <span className={styles.warning}>Final desconocido</span>}
        {!ended && <Link href={"/live/jobs/" + encodeURIComponent(jobId)}>Volver al análisis en vivo</Link>}
      </div>}
    </header>}>
    {error && <p role="alert">{error}</p>}
    {!result && !error && <p role="status">Cargando resultados…</p>}
    {result && <>
      <section aria-label="Indicadores de captura"><dl className={styles.metrics}>
        <div className={styles.metric}><dt>Cruces totales</dt><dd aria-label="Total de cruces">{summary?.total_crossings ?? "--"}</dd>
          <dd className={styles.metricNote}>{access ? "Entradas: " + (summary?.entry_count ?? "--") + " · Salidas: " + (summary?.exit_count ?? "--") :
            "A → B: " + (summary?.a_to_b_count ?? "--") + " · B → A: " + (summary?.b_to_a_count ?? "--")}</dd></div>
        <div className={styles.metric}><dt>Permanencia interna</dt><dd aria-label="Estadía promedio interna">{duration(dwell?.interior_average_seconds)}</dd>
          <dd className={styles.metricNote}>{visitNote(dwell?.interior_sample_count)}</dd></div>
        <div className={styles.metric}><dt>Permanencia externa</dt><dd aria-label="Estadía promedio externa">{duration(dwell?.front_average_seconds)}</dd>
          <dd className={styles.metricNote}>{visitNote(dwell?.front_sample_count)}</dd></div>
        <div className={styles.metric}><dt>Cobertura del análisis</dt><dd aria-label="Cobertura del análisis">{coverage}</dd>
          <dd className={styles.metricNote}>{unanalyzed}</dd></div>
      </dl></section>
      <div className={styles.content}>
        <section className={styles.panel} aria-labelledby={selectId + "-flow"}>
          <header className={styles.panelHeader}><h2 id={selectId + "-flow"}>Flujo de cruces temporales</h2>
            <ZoneSelect id={selectId} className={styles.lineSelect} value={result.selected_shop_id ?? ""} options={result.shops.map((shop) => ({ id: shop.shop_id, name: shop.shop_name }))} onChange={setShopId} /></header>
          {summary ? <CrossingChart minutes={result.minutes} summary={summary} captureStartedAt={captureDate} report /> :
            <div className={styles.chartEmpty}>Sin cruces guardados para esta línea.</div>}
          {result.next_bucket_cursor !== null && <button type="button" data-primary disabled={loadingMore} onClick={() => void moreMinutes()}>Cargar más minutos</button>}
        </section>
        <section className={styles.panel} aria-labelledby={selectId + "-map"}>
          <header className={styles.panelHeader}><h2 id={selectId + "-map"}>Mapa de posiciones</h2></header>
          {sampleError && <p role="alert">{sampleError}</p>}
          {samples?.availability === "available" && samples.samples.length > 0 ? <figure className={styles.frame}>
            <img alt="Frame de referencia de la escena" src={apiBaseUrl + "/sessions/" + encodeURIComponent(result.session_id) + "/reference-frame"} />
            <PositionHeatmap availability={samples.availability} samples={samples.samples} />
          </figure> : !sampleError && <div className={styles.emptyMap}><EmptyState title={samples ? "Sin muestra de posiciones" : "Cargando posiciones…"} icon={<MapPinOff size={32} strokeWidth={1.5} aria-hidden="true" />}>{!samples ? "Consultando la muestra guardada." : samples.availability === "unavailable" ?
              "No hay una muestra de posiciones disponible para esta captura." : "No se registraron trayectorias continuas durante el lapso de captura."}</EmptyState></div>}
        </section>
      </div>
      <details className={styles.diagnostics}>
        <summary><Activity size={18} aria-hidden="true" /><span>Diagnóstico técnico de la captura (Interrupciones y descarte)</span><ChevronDown className={styles.chevron} size={18} aria-hidden="true" /></summary>
        <div className={styles.diagnosticBody}>
          <dl className={styles.audit}>
            <div><dt>Intervalos sin cobertura</dt><dd>{result.interruptions.length ? <ul>{result.interruptions.map(gap =>
              <li key={gap.id}>{gap.start_seconds.toFixed(1)} s ➔ {gap.end_known && gap.end_seconds !== null ? gap.end_seconds.toFixed(1) + " s" : "Final desconocido"} <code>({gap.reason === "operator_pause" ? "Pausa del operador" : gap.reason})</code></li>)}</ul> : "Sin interrupciones registradas"}</dd></div>
            <div><dt>Cruces sin confirmar descartados</dt><dd>{result.unconfirmed_crossings}</dd></div>
            <div><dt>Registro de eventos</dt><dd>{summary ? summary.total_crossings + " cruces individuales" : "Sin datos"}</dd></div>
            <div><dt>Muestra de posiciones</dt><dd>{samples ? samples.returned_count + " posiciones mostradas de " + samples.sample_count + " muestras guardadas; capacidad " + samples.capacity + "." : "No disponible"}</dd></div>
            <div><dt>Asistente analítico</dt><dd>Asistente analítico no disponible para sesiones en tiempo real.</dd></div>
          </dl>
          <p className={styles.note}>No representa personas únicas. El total suma cruces confirmados de la línea seleccionada. La permanencia usa visitas de duración positiva, incluidas las visitas en curso; los períodos sin seguimiento cortan la continuidad.</p>
          {result.unknown_tail && <p className={styles.warning}>Final desconocido: la duración y las cifras corresponden al último checkpoint válido.</p>}
          <section aria-label="Registro de cruces"><h3>Cruces individuales</h3>
            {eventError && <p role="alert">{eventError}</p>}
            {!events && !eventError && <p role="status">Cargando cruces…</p>}
            {events?.events.length === 0 && <p className={styles.note}>No hay cruces confirmados para esta línea.</p>}
            {events && events.events.length > 0 && <EventsTable label="Cruces individuales"><thead><tr><th>Captura (s)</th><th>Confirmación (s)</th><th>Sentido</th></tr></thead>
              <tbody>{events.events.map(event => <tr key={event.id}><td>{event.capture_timestamp_seconds.toFixed(2)}</td><td>{event.confirmed_at_capture_seconds.toFixed(2)}</td>
                <td>{access ? event.direction === "entry" ? "Entrada" : "Salida" :
                  (event.direction === "entry") === (summary?.entry_direction === "a_to_b") ? "A → B" : "B → A"}</td></tr>)}</tbody></EventsTable>}
            {events?.next_cursor && <button type="button" data-primary disabled={loadingMore} onClick={() => void moreEvents()}>Cargar más cruces</button>}
          </section>
          {summary && result.minutes.length > 0 && <section aria-label="Cobertura por minuto"><h3>Datos y cobertura por minuto</h3>
            <p className={styles.note}>El minuto en curso puede cambiar al confirmarse un cruce. Los intervalos sin análisis no representan cero personas.</p>
            <EventsTable label="Cobertura por minuto"><thead><tr><th>Minuto</th><th>{access ? "Entradas" : "A → B"}</th><th>{access ? "Salidas" : "B → A"}</th><th>Cobertura</th></tr></thead>
              <tbody>{result.minutes.map(minute => <tr key={minute.bucket_index}><th>{minuteTime(minute.start_seconds)}</th>
                <td>{minute.observed_seconds === 0 ? "Sin datos" : access || summary.entry_direction === "a_to_b" ? minute.entries : minute.exits}</td>
                <td>{minute.observed_seconds === 0 ? "Sin datos" : access || summary.entry_direction === "a_to_b" ? minute.exits : minute.entries}</td>
                <td>{minute.coverage_incomplete || minute.unknown_tail ? "Cobertura incompleta" : minute.is_open ? "Minuto en curso" : "Minuto cerrado"}</td></tr>)}</tbody></EventsTable>
          </section>}
        </div>
      </details>
    </>}
  </AppShell>;
}
