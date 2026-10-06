import { useEffect, useId, useState } from "react";
import { API_BASE_URL } from "../api/config";
import { requestJson } from "../api/http";
import { getLiveResults } from "../api/live";
import { AppShell } from "../components/AppShell";
import { CrossingChart } from "../components/CrossingChart";
import { Link } from "../components/Link";
import { PositionHeatmap } from "../components/PositionHeatmap";
import { LiveDwellSummary } from "../components/LiveDwellSummary";
import type { LiveResults } from "../types/live";
import styles from "./LiveAnalysisPage.module.css";

interface LiveSamples { job_id: string; source_kind: "webcam"; time_basis: "capture";
  availability: "available" | "unavailable"; sample_count: number; returned_count: number;
  candidate_count: number; capacity: number; samples: { capture_timestamp_seconds: number; foot: [number, number] }[]; }
interface LiveEvents { events: { id: string; track_id: number; capture_timestamp_seconds: number;
  confirmed_at_capture_seconds: number; direction: "entry" | "exit" }[]; next_cursor: string | null; }

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
  return <AppShell title="Resultados de webcam" context="Resultados de webcam">
    <Link href="/">Mis análisis</Link>
    <p>Sin grabación · No representa personas únicas. El total suma cruces confirmados de la línea seleccionada.</p>
    {error && <p role="alert">{error}</p>}
    {!result && !error && <p role="status">Cargando resultados…</p>}
    {result && <>
      <p role="status">{result.result_complete ? "Análisis completo" : "Resultados parciales"}</p>
      <LiveDwellSummary dwell={result.zone_dwell?.[result.selected_shop_id ?? ""]} />
      {!["completed", "failed", "cancelled"].includes(result.status) && <Link href={`/live/jobs/${encodeURIComponent(jobId)}`}>Volver al análisis en vivo</Link>}
      <p>Duración de captura guardada: {result.elapsed_capture_seconds.toFixed(1)} segundos · Observados: {result.observed_seconds.toFixed(1)} s · Sin cobertura: {result.missing_seconds.toFixed(1)} s</p>
      {!result.coverage_complete && <p className={styles.warning}>Cobertura incompleta: hay intervalos sin observaciones.</p>}
      {result.unknown_tail && <p className={styles.warning}>Final desconocido: la duración y las cifras corresponden al último checkpoint válido.</p>}
      <label htmlFor={selectId}>Línea de conteo</label><select id={selectId} value={result.selected_shop_id ?? ""} onChange={(event) => setShopId(event.target.value)}>
        {result.shops.map((shop) => <option key={shop.shop_id} value={shop.shop_id}>{shop.shop_name}</option>)}
      </select>
      {summary && <section className={styles.panel} aria-label="Cruces guardados"><dl className={styles.metrics}>
        <div><dt>{access ? "Entradas" : "A → B"}</dt><dd>{access ? summary.entry_count : summary.a_to_b_count}</dd></div>
        <div><dt>{access ? "Salidas" : "B → A"}</dt><dd>{access ? summary.exit_count : summary.b_to_a_count}</dd></div>
        <div><dt>Total</dt><dd aria-label="Total de cruces">{summary.total_crossings}</dd></div>
      </dl><CrossingChart minutes={result.minutes} summary={summary} captureStartedAt={result.capture_started_at} />
        {result.next_bucket_cursor !== null && <button type="button" disabled={loadingMore} onClick={() => void moreMinutes()}>Cargar más minutos</button>}
      </section>}
      <section><h2>Interrupciones</h2>{result.interruptions.length === 0 ? <p>Sin interrupciones registradas.</p> :
        <ul>{result.interruptions.map((gap) => <li key={gap.id}>{gap.start_seconds.toFixed(1)} s → {gap.end_known && gap.end_seconds !== null ? `${gap.end_seconds.toFixed(1)} s` : "Final desconocido"} ({gap.reason})</li>)}</ul>}
        <p>Cruces sin confirmar descartados: {result.unconfirmed_crossings}</p>
      </section>
      <section><h2>Mapa de posiciones muestreadas</h2><p>Posiciones observadas sobre el frame de referencia. No mide visitantes únicos ni permanencia exacta.</p>
        {sampleError && <p role="alert">{sampleError}</p>}
        {samples?.samples.length ? <>
          <div style={{ position: "relative", maxWidth: 960 }}><img style={{ width: "100%", display: "block" }}
            alt="Frame de referencia de la escena" src={`${apiBaseUrl}/sessions/${encodeURIComponent(result.session_id)}/reference-frame`} />
            <PositionHeatmap availability={samples.availability} samples={samples.samples} />
          </div><p>{samples.returned_count} posiciones mostradas de {samples.sample_count} muestras guardadas; capacidad {samples.capacity}.</p>
        </> : !sampleError && <p>No hay posiciones válidas guardadas para esta sesión.</p>}
      </section>
      <section><h2>Cruces individuales</h2>{eventError && <p role="alert">{eventError}</p>}
        {events?.events.length === 0 && <p>No hay cruces confirmados para esta línea.</p>}
        {events && events.events.length > 0 && <table><thead><tr><th>Captura (s)</th><th>Confirmación (s)</th><th>Sentido</th></tr></thead>
          <tbody>{events.events.map((event) => <tr key={event.id}><td>{event.capture_timestamp_seconds.toFixed(2)}</td><td>{event.confirmed_at_capture_seconds.toFixed(2)}</td>
            <td>{access ? event.direction === "entry" ? "Entrada" : "Salida" :
              (event.direction === "entry") === (summary?.entry_direction === "a_to_b") ? "A → B" : "B → A"}</td></tr>)}</tbody></table>}
        {events?.next_cursor && <button type="button" disabled={loadingMore} onClick={() => void moreEvents()}>Cargar más cruces</button>}
      </section>
      <p>El chat no está disponible para las sesiones de webcam.</p>
    </>}
  </AppShell>;
}
