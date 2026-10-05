import { useEffect, useId, useRef, useState } from "react";
import { API_BASE_URL } from "../api/config";
import { getLiveResults, resumeWebcam, retryWebcam, stopWebcam } from "../api/live";
import { previewUrl } from "../api/jobs";
import { acceptLiveUpdate, ClockCalibration, parseLiveMessage, type LiveReconnectCheck, type LiveUpdate } from "../api/liveMessages";
import { AppShell } from "../components/AppShell";
import { CrossingChart } from "../components/CrossingChart";
import { Link } from "../components/Link";
import type { LiveResults } from "../types/live";
import styles from "./LiveAnalysisPage.module.css";

const terminal = (status: string) => ["completed", "failed", "cancelled"].includes(status);
function object(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null; }

export function LiveAnalysisPage({ jobId, apiBaseUrl = API_BASE_URL }: { jobId: string; apiBaseUrl?: string }) {
  const [durable, setDurable] = useState<LiveResults | null>(null);
  const [snapshot, setSnapshot] = useState<LiveUpdate | null>(null);
  const [shopId, setShopId] = useState<string>("");
  const [connection, setConnection] = useState("Conectando");
  const [captureStatus, setCaptureStatus] = useState("starting");
  const [finalStatus, setFinalStatus] = useState<string | null>(null);
  const [stopping, setStopping] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(performance.now());
  const [stopStarted, setStopStarted] = useState<number | null>(null);
  const [reconnectCheck, setReconnectCheck] = useState<{ message: LiveReconnectCheck; expiresAt: number } | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [resuming, setResuming] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [transportReady, setTransportReady] = useState(false);
  const [paintLatency, setPaintLatency] = useState<{ estimated_ms: number; uncertainty_ms: number } | null>(null);
  const paintHandles = useRef<number[]>([]);
  const lastPainted = useRef<string | null>(null);
  const recovery = useRef<LiveReconnectCheck | null>(null);
  const current = useRef<LiveUpdate | null>(null);
  const calibration = useRef(new ClockCalibration());
  const receivedAt = useRef(0);
  const selectId = useId();
  const confirmationId = useId();

  useEffect(() => {
    let disposed = false, ended = false, attempt = 0;
    let minimumRevision = 0;
    let socket: WebSocket | null = null;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let pingTimer: ReturnType<typeof setInterval> | undefined;
    const timers = new Set<ReturnType<typeof setTimeout>>();
    current.current = null; calibration.current = new ClockCalibration();
    setSnapshot(null); setDurable(null); setFinalStatus(null); setStopping(false); setError(null);
    recovery.current = null; setReconnectCheck(null); setConfirmed(false); setResuming(false); setRetrying(false); setTransportReady(false);
    lastPainted.current = null; setPaintLatency(null);
    async function refresh(): Promise<LiveResults | null> {
      try {
        const result = await getLiveResults(apiBaseUrl, jobId);
        if (disposed) return null;
        minimumRevision = Math.max(minimumRevision, result.revision);
        setDurable(result); setShopId((selected) => selected || result.selected_shop_id || "");
        setCaptureStatus(result.capture_status);
        if (terminal(result.status)) {
          ended = true; setFinalStatus(result.status); setSnapshot(null); setReconnectCheck(null); socket?.close();
        }
        return result;
      } catch (cause) { if (!disposed) setError(cause instanceof Error ? cause.message : "No se pudieron consultar los resultados."); return null; }
    }
    function scheduleReconnect() {
      if (disposed || ended) return;
      retry = setTimeout(() => {
        void refresh().then((result) => {
          if (disposed || ended) return;
          if (result) connect(result.session_id);
          else scheduleReconnect();
        });
      }, [1000, 2000, 5000][Math.min(attempt++, 2)]);
    }
    function connect(sessionId: string) {
      if (disposed || ended) return;
      calibration.current = new ClockCalibration();
      socket = new WebSocket(previewUrl(apiBaseUrl, jobId));
      const connectedSocket = socket;
      const ping = () => {
        if (disposed || ended || connectedSocket.readyState !== 1) return;
        const clientTime = performance.now(), nonce = crypto.randomUUID();
        calibration.current.sent(nonce, clientTime);
        connectedSocket.send(JSON.stringify({ type: "clock.ping", nonce, client_sent_ms: clientTime }));
      };
      connectedSocket.onopen = () => {
        if (disposed) return;
        attempt = 0; setConnection("Conectado"); setError(null);
        setTransportReady(true);
        for (let index = 0; index < 8; index++) {
          const timer = setTimeout(() => { timers.delete(timer); ping(); }, index * 100);
          timers.add(timer);
        }
        pingTimer = setInterval(ping, 31000);
      };
      connectedSocket.onmessage = (event) => {
        if (disposed || ended || typeof event.data !== "string" || event.data.length > 1048576) return;
        let value: unknown;
        try { value = JSON.parse(event.data) as unknown; } catch { return; }
        const parsed = parseLiveMessage(value);
        if (parsed?.type === "clock.pong") { calibration.current.received(parsed, performance.now()); return; }
        if (parsed?.type === "live.update") {
          if (parsed.revision < minimumRevision) return;
          if (!acceptLiveUpdate(current.current, parsed, jobId, sessionId)) return;
          if (recovery.current && (parsed.revision <= recovery.current.revision || parsed.segment_index !== recovery.current.segment_index)) return;
          current.current = parsed; receivedAt.current = performance.now();
          recovery.current = null; setReconnectCheck(null); setConfirmed(false); setResuming(false);
          setSnapshot(parsed); setCaptureStatus("connected"); setConnection("Conectado"); return;
        }
        if (parsed?.type === "live.reconnect-check") {
          if (parsed.revision < minimumRevision || parsed.job_id !== jobId || parsed.session_id !== sessionId ||
            (current.current && (parsed.revision < current.current.revision || parsed.segment_index <= current.current.segment_index))) return;
          recovery.current = parsed;
          setReconnectCheck({ message: parsed, expiresAt: performance.now() + parsed.expires_in_seconds * 1000 });
          setConfirmed(false); setResuming(false); setRetrying(false); setTransportReady(true);
          setCaptureStatus("awaiting_confirmation"); setConnection("Esperando confirmación del encuadre"); return;
        }
        if (!object(value) || value.job_id !== jobId || value.session_id !== sessionId) return;
        if (value.type === "job.terminal" && typeof value.status === "string" && terminal(value.status)) {
          ended = true; setFinalStatus(value.status); setSnapshot(null); setReconnectCheck(null); void refresh(); connectedSocket.close();
        } else if (value.type === "live.status" && typeof value.capture_status === "string") {
          setCaptureStatus(value.capture_status);
          if (value.capture_status !== "connected") setConnection("Captura interrumpida");
        }
      };
      connectedSocket.onclose = () => {
        if (pingTimer) clearInterval(pingTimer);
        for (const timer of timers) clearTimeout(timer); timers.clear();
        if (disposed || ended) return;
        setTransportReady(false);
        setConnection("Conexión perdida · reconectando");
        // Keep the previous atomic frame/counters until a newer pair arrives.
        scheduleReconnect();
      };
    }
    void refresh().then((result) => {
      if (disposed || ended) return;
      if (result) connect(result.session_id);
      else scheduleReconnect();
    });
    const clockTick = setInterval(() => { if (!disposed) setNow(performance.now()); }, 250);
    return () => {
      disposed = true; clearInterval(clockTick); if (retry) clearTimeout(retry);
      if (pingTimer) clearInterval(pingTimer); for (const timer of timers) clearTimeout(timer);
      socket?.close();
      for (const handle of paintHandles.current) cancelAnimationFrame(handle);
      paintHandles.current = [];
    };
  }, [apiBaseUrl, jobId]);

  const shops = snapshot?.shops ?? durable?.shops ?? [];
  const summary = snapshot ? snapshot.shops.find((shop) => shop.shop_id === shopId) ?? null :
    durable?.selected_shop_id === shopId ? durable.summary : null;
  const minutes = snapshot ? snapshot.minutes.filter((minute) => minute.shop_id === shopId) : durable?.minutes ?? [];
  const stale = snapshot !== null && (connection !== "Conectado" || captureStatus !== "connected" || now - receivedAt.current > 2000);
  const age = snapshot === null ? null : calibration.current.age(snapshot.captured_monotonic_ms, now);
  const labels = summary?.label_mode === "access" ? ["Entradas", "Salidas"] : ["A → B", "B → A"];
  async function selectShop(value: string) {
    setShopId(value);
    if (!snapshot) {
      try { const result = await getLiveResults(apiBaseUrl, jobId, value); setDurable(result); }
      catch (cause) { setError(cause instanceof Error ? cause.message : "No se pudieron consultar los cruces."); }
    }
  }
  async function stop() {
    setStopping(true); setStopStarted(performance.now()); setError(null);
    try { await stopWebcam(apiBaseUrl, jobId); }
    catch (cause) { setStopping(false); setStopStarted(null); setError(cause instanceof Error ? cause.message : "No se pudo solicitar la detención."); }
  }
  function imageLoaded(frame: LiveUpdate) {
    for (const handle of paintHandles.current) cancelAnimationFrame(handle);
    paintHandles.current = [requestAnimationFrame(() => {
      paintHandles.current = [requestAnimationFrame(() => {
        paintHandles.current = [];
        const key = `${frame.job_id}:${frame.segment_index}:${frame.capture_sequence}`;
        if (document.hidden || current.current !== frame || lastPainted.current === key) return;
        lastPainted.current = key;
        const measured = calibration.current.age(frame.captured_monotonic_ms, performance.now());
        setPaintLatency(measured);
        window.dispatchEvent(new CustomEvent("flowsight:live-latency", { detail: {
          job_id: frame.job_id, capture_sequence: frame.capture_sequence,
          measured: measured !== null, estimated_ms: measured?.estimated_ms ?? null,
          uncertainty_ms: measured?.uncertainty_ms ?? null, upper_bound_ms: measured?.upper_bound_ms ?? null,
        } }));
      })];
    })];
  }
  async function retryCamera() {
    setRetrying(true); setError(null);
    try {
      await retryWebcam(apiBaseUrl, jobId);
      setReconnectCheck(null); setConfirmed(false); setResuming(false);
      setCaptureStatus("interrupted"); setConnection("Reintentando cámara");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "No se pudo reintentar la cámara."); }
    finally { setRetrying(false); }
  }
  async function resumeCamera() {
    if (!reconnectCheck || !confirmed || performance.now() >= reconnectCheck.expiresAt) return;
    setResuming(true); setError(null);
    try { await resumeWebcam(apiBaseUrl, jobId, reconnectCheck.message.check_token); }
    catch (cause) { setResuming(false); setConfirmed(false); setError(cause instanceof Error ? cause.message : "No se pudo reanudar la cámara."); }
  }
  return <AppShell title="Análisis en vivo" context="Webcam">
    <div className={styles.controls}><Link href="/">Mis análisis</Link>
      <button type="button" disabled={stopping || finalStatus !== null || durable === null} onClick={() => void stop()}>Detener análisis</button>
      <p role="status">{finalStatus === "completed" ? "Análisis finalizado" : finalStatus === "failed" ? "Análisis fallido · resultados parciales" :
        finalStatus === "cancelled" ? "Análisis cancelado" : stopping ? "Finalizando" : connection}</p>
    </div>
    {error && <p role="alert">{error}</p>}
    {finalStatus === null && ["interrupted", "awaiting_confirmation"].includes(captureStatus) && <section aria-label="Recuperación de cámara">
      <h2>Revisar cámara</h2>
      <p>Los cruces anteriores se conservan. Una interrupción comienza un segmento nuevo de seguimiento.</p>
      {reconnectCheck && <>
        <div className={styles.camera}><img alt="Encuadre para reanudar" src={`data:image/jpeg;base64,${reconnectCheck.message.image_base64}`} /></div>
        <p>Comprobación de encuadre: esta imagen no agrega detecciones ni cruces.</p>
        <input id={confirmationId} type="checkbox" checked={confirmed} disabled={stopping || resuming || now >= reconnectCheck.expiresAt}
          onChange={(event) => setConfirmed(event.target.checked)} />
        <label htmlFor={confirmationId}>Confirmo que el encuadre coincide con la configuración</label>
        <button type="button" disabled={!confirmed || !transportReady || stopping || resuming || now >= reconnectCheck.expiresAt}
          onClick={() => void resumeCamera()}>Reanudar análisis</button>
        {now >= reconnectCheck.expiresAt && <p role="status">La comprobación venció. Pedí otro intento de cámara.</p>}
        {resuming && <p role="status">Reanudación solicitada. Esperando el primer frame analizado.</p>}
      </>}
      <button type="button" disabled={stopping || retrying || resuming || !transportReady}
        onClick={() => void retryCamera()}>Reintentar cámara</button>
    </section>}
    {stopping && finalStatus === null && stopStarted !== null && now - stopStarted > 10000 &&
      <p className={styles.warning}>La detención fue solicitada. Esperando que termine la inferencia y se guarden los resultados.</p>}
    <div className={styles.layout}><section aria-label="Vista de cámara">
      <div className={styles.camera}>{snapshot && finalStatus === null ?
        <img alt="Cámara en vivo" src={`data:image/jpeg;base64,${snapshot.image_base64}`} onLoad={() => imageLoaded(snapshot)} /> :
        <p>{finalStatus ? "Captura terminada. El video no se graba." : "Esperando el primer frame analizado…"}</p>}</div>
      {stale && <p className={styles.warning}>Imagen desactualizada · los contadores corresponden al último frame mostrado.</p>}
      <p className={styles.diagnostics}>Sin grabación · los cruces cuentan pasos por la línea, no personas únicas.</p>
      <p className={styles.diagnostics}>{paintLatency ? `Captura a pantalla: ${Math.round(paintLatency.estimated_ms)} ms (±${Math.ceil(paintLatency.uncertainty_ms)} ms)` : "Captura a pantalla: todavía sin muestra calibrada"}</p>
      <p className={styles.diagnostics}>{snapshot && <>Captura: {snapshot.capture_fps?.toFixed(1) ?? "—"} FPS · Análisis: {snapshot.analysis_fps?.toFixed(1) ?? "—"} FPS · </>}
        {age ? `Antigüedad estimada del frame: ${Math.round(age.estimated_ms)} ms (±${Math.ceil(age.uncertainty_ms)} ms)` : "Antigüedad del frame: esperando calibración del reloj"}</p>
    </section><aside className={styles.panel} aria-label="Estadísticas en vivo">
      <label htmlFor={selectId}>Línea de conteo</label><select id={selectId} value={shopId} onChange={(event) => void selectShop(event.target.value)}>
        {shops.map((shop) => <option key={shop.shop_id} value={shop.shop_id}>{shop.shop_name}</option>)}
      </select>
      {summary ? <><dl className={styles.metrics}>
        <div><dt>{labels[0]}</dt><dd aria-label={labels[0]}>{summary.label_mode === "access" ? summary.entry_count : summary.a_to_b_count}</dd></div>
        <div><dt>{labels[1]}</dt><dd aria-label={labels[1]}>{summary.label_mode === "access" ? summary.exit_count : summary.b_to_a_count}</dd></div>
        <div><dt>Total</dt><dd aria-label="Total de cruces">{summary.total_crossings}</dd></div>
      </dl><CrossingChart minutes={minutes} summary={summary} /></> : <p>Configurá una línea para mostrar los cruces.</p>}
      {!(snapshot?.coverage_complete ?? durable?.coverage_complete ?? true) && <p className={styles.warning}>Cobertura incompleta: hubo intervalos sin analizar.</p>}
      <p className={styles.diagnostics}>Último guardado: {snapshot?.checkpoint_at ?? durable?.checkpoint_at ?? "Todavía no hay un checkpoint"}</p>
    </aside></div>
    {finalStatus && <Link href={`/live/jobs/${encodeURIComponent(jobId)}/results`}>Ver resultados guardados</Link>}
  </AppShell>;
}
