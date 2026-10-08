import { useEffect, useId, useRef, useState } from "react";
import { API_BASE_URL } from "../api/config";
import { continueWebcam, getLiveResults, pauseWebcam, resumeWebcam, retryWebcam, stopWebcam } from "../api/live";
import { previewUrl } from "../api/jobs";
import { acceptLiveUpdate, ClockCalibration, parseLiveMessage, type LiveReconnectCheck, type LiveUpdate } from "../api/liveMessages";
import { AppShell } from "../components/AppShell";
import { CrossingChart } from "../components/CrossingChart";
import { Link } from "../components/Link";
import { LiveDwellSummary } from "../components/LiveDwellSummary";
import { PositionHeatmap } from "../components/PositionHeatmap";
import { requestJson } from "../api/http";
import { getSession } from "../api/sessions";
import type { SessionDetail } from "../types/session";
import { Activity, ArrowLeft, Clock, Flame, VideoOff, AlertTriangle, Radio, Pause, Play } from "lucide-react";
import type { LiveResults } from "../types/live";
import styles from "./LiveAnalysisPage.module.css";

const terminal = (status: string) => ["completed", "failed", "cancelled"].includes(status);
function object(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null; }

export function LiveAnalysisPage({ jobId, apiBaseUrl = API_BASE_URL }: { jobId: string; apiBaseUrl?: string }) {
  const [durable, setDurable] = useState<LiveResults | null>(null);
  const [snapshot, setSnapshot] = useState<LiveUpdate | null>(null);
  const [shopId, setShopId] = useState<string>("");
  const selectedShop = useRef("");
  const [connection, setConnection] = useState("Conectando");
  const [captureStatus, setCaptureStatus] = useState("starting");
  const [finalStatus, setFinalStatus] = useState<string | null>(null);
  const [stopping, setStopping] = useState(false);
  const [pauseRequested, setPauseRequested] = useState(false);
  const [continuing, setContinuing] = useState(false);
  const capturePhase = useRef("starting");
  const commandPending = useRef(false);
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
  const heatmapId = useId();
  const [showHeatmap, setShowHeatmap] = useState(false);
  const [samples, setSamples] = useState<{ capture_timestamp_seconds: number; foot: [number, number] }[]>([]);
  const [sampleError, setSampleError] = useState<string | null>(null);
  const [session, setSession] = useState<SessionDetail | null>(null);
  useEffect(() => {
    let active = true;
    if (!durable?.session_id) return;
    void getSession(apiBaseUrl, durable.session_id).then(value => {
      if (active && value.camera) setSession(value);
    }).catch(() => { /* Los resultados y el transporte siguen disponibles sin metadatos. */ });
    return () => { active = false; };
  }, [apiBaseUrl, durable?.session_id]);

  useEffect(() => {
    let disposed = false;
    setSamples([]); setSampleError(null);
    if (!showHeatmap) return;
    async function refreshSamples() {
      try {
        const value = await requestJson<{ job_id: string; source_kind: string; time_basis: string;
          samples: { capture_timestamp_seconds: number; foot: [number, number] }[] }>(
          `${apiBaseUrl}/jobs/${encodeURIComponent(jobId)}/position-samples`);
        if (value.job_id !== jobId || value.source_kind !== "webcam" || value.time_basis !== "capture" ||
          !Array.isArray(value.samples) || value.samples.length > 2000 || value.samples.some((sample) =>
            !Number.isFinite(sample.capture_timestamp_seconds) || sample.capture_timestamp_seconds < 0 ||
            !Array.isArray(sample.foot) || sample.foot.length !== 2 || sample.foot.some((point) => !Number.isFinite(point) || point < 0 || point > 1))) {
          throw new Error("Muestra de posiciones inválida");
        }
        if (!disposed) { setSamples(value.samples); setSampleError(null); }
      } catch { if (!disposed) setSampleError("No se pudo actualizar el mapa de calor."); }
    }
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      await refreshSamples();
      if (!disposed) timer = setTimeout(() => void poll(), 2000);
    }
    void poll();
    return () => { disposed = true; clearTimeout(timer); };
  }, [apiBaseUrl, jobId, showHeatmap]);

  useEffect(() => {
    let disposed = false, ended = false, attempt = 0;
    let minimumRevision = 0;
    let socket: WebSocket | null = null;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let pingTimer: ReturnType<typeof setInterval> | undefined;
    const timers = new Set<ReturnType<typeof setTimeout>>();
    current.current = null; calibration.current = new ClockCalibration();
    selectedShop.current = "";
    setSnapshot(null); setDurable(null); setFinalStatus(null); setStopping(false); setError(null);
    capturePhase.current = "starting"; commandPending.current = false;
    setPauseRequested(false); setContinuing(false);
    recovery.current = null; setReconnectCheck(null); setConfirmed(false); setResuming(false); setRetrying(false); setTransportReady(false);
    lastPainted.current = null; setPaintLatency(null);
    async function refresh(): Promise<LiveResults | null> {
      try {
        const result = await getLiveResults(apiBaseUrl, jobId, selectedShop.current || undefined);
        if (disposed) return null;
        if (result.revision < minimumRevision && !terminal(result.status)) return result;
        minimumRevision = Math.max(minimumRevision, result.revision);
        setDurable(result); setShopId((selected) => selected || result.selected_shop_id || "");
        if (!selectedShop.current) selectedShop.current = result.selected_shop_id || "";
        setCaptureStatus(result.capture_status);
        if (result.capture_status === "paused") setSnapshot(null);
        capturePhase.current = result.capture_status;
        setPauseRequested(result.capture_status === "pausing");
        setContinuing(result.resume_requested === true && result.capture_status === "paused");
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
          if (["pausing", "paused", "stopping", "ended"].includes(capturePhase.current)) return;
          if (!acceptLiveUpdate(current.current, parsed, jobId, sessionId)) return;
          if (recovery.current && (parsed.revision <= recovery.current.revision || parsed.segment_index !== recovery.current.segment_index)) return;
          current.current = parsed; receivedAt.current = performance.now();
          recovery.current = null; setReconnectCheck(null); setConfirmed(false); setResuming(false);
          setSnapshot(parsed); capturePhase.current = "connected";
          setPauseRequested(false); setContinuing(false); commandPending.current = false;
          setCaptureStatus("connected"); setConnection("Conectado"); return;
        }
        if (parsed?.type === "live.reconnect-check") {
          if (parsed.revision < minimumRevision || parsed.job_id !== jobId || parsed.session_id !== sessionId ||
            (current.current && (parsed.revision < current.current.revision || parsed.segment_index <= current.current.segment_index))) return;
          recovery.current = parsed;
          minimumRevision = Math.max(minimumRevision, parsed.revision);
          capturePhase.current = "awaiting_confirmation";
          setContinuing(false); setPauseRequested(false); commandPending.current = false;
          setReconnectCheck({ message: parsed, expiresAt: performance.now() + parsed.expires_in_seconds * 1000 });
          setConfirmed(false); setResuming(false); setRetrying(false); setTransportReady(true);
          setCaptureStatus("awaiting_confirmation"); setConnection("Esperando confirmación del encuadre"); return;
        }
        if (parsed?.type === "live.status") {
          if (parsed.job_id !== jobId || parsed.session_id !== sessionId || parsed.revision < minimumRevision ||
            (current.current && parsed.revision < current.current.revision)) return;
          if (parsed.capture_status === "connected" && ["pausing", "paused", "stopping"].includes(capturePhase.current)) return;
          minimumRevision = Math.max(minimumRevision, parsed.revision);
          capturePhase.current = parsed.capture_status;
          setCaptureStatus(parsed.capture_status);
          setPauseRequested(parsed.capture_status === "pausing");
          if (parsed.capture_status === "paused") {
            commandPending.current = false;
            // The last in-flight inference is durable even when its JPEG was suppressed.
            void refresh();
          }
          if (parsed.capture_status !== "connected") setPaintLatency(null);
          if (parsed.capture_status === "stopping") setStopping(true);
          if (["interrupted", "awaiting_confirmation"].includes(parsed.capture_status)) setContinuing(false);
          if (terminal(parsed.status)) {
            ended = true; setFinalStatus(parsed.status); setSnapshot(null); connectedSocket.close(); void refresh();
          }
          return;
        }
        if (!object(value) || value.job_id !== jobId || value.session_id !== sessionId) return;
        if (value.type === "job.terminal" && typeof value.status === "string" && terminal(value.status)) {
          ended = true; setFinalStatus(value.status); setSnapshot(null); setReconnectCheck(null); void refresh(); connectedSocket.close();
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
    selectedShop.current = value;
    setShopId(value);
    if (!snapshot) {
      try { const result = await getLiveResults(apiBaseUrl, jobId, value); setDurable(result); }
      catch (cause) { setError(cause instanceof Error ? cause.message : "No se pudieron consultar los cruces."); }
    }
  }
  async function stop() {
    capturePhase.current = "stopping";
    setStopping(true); setStopStarted(performance.now()); setError(null);
    try { await stopWebcam(apiBaseUrl, jobId); }
    catch (cause) { capturePhase.current = captureStatus; setStopping(false); setStopStarted(null); setError(cause instanceof Error ? cause.message : "No se pudo solicitar la detención."); }
  }
  async function pauseAnalysis() {
    if (commandPending.current || stopping || finalStatus !== null || captureStatus !== "connected") return;
    commandPending.current = true; capturePhase.current = "pausing";
    setPauseRequested(true); setError(null);
    try { await pauseWebcam(apiBaseUrl, jobId); }
    catch (cause) {
      commandPending.current = false; capturePhase.current = captureStatus; setPauseRequested(false);
      setError(cause instanceof Error ? cause.message : "No se pudo solicitar la pausa.");
    }
  }
  async function continueAnalysis() {
    if (commandPending.current || stopping || finalStatus !== null || captureStatus !== "paused") return;
    commandPending.current = true; setContinuing(true); setError(null);
    try { await continueWebcam(apiBaseUrl, jobId); }
    catch (cause) {
      commandPending.current = false; setContinuing(false);
      setError(cause instanceof Error ? cause.message : "No se pudo retomar el análisis.");
    }
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
  const checkpoint = snapshot?.checkpoint_at ?? durable?.checkpoint_at;
  const checkpointDate = checkpoint ? new Date(checkpoint) : null;
  const syncTime = checkpointDate && Number.isFinite(checkpointDate.getTime()) ? new Intl.DateTimeFormat("es-AR", {
    hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23", timeZone: "America/Argentina/Buenos_Aires",
  }).format(checkpointDate) + " hs" : "--";
  const active = finalStatus === null && !stopping && !pauseRequested && captureStatus === "connected" && connection === "Conectado" && !stale;
  const paused = finalStatus === null && captureStatus === "paused";
  const pausing = finalStatus === null && (pauseRequested || captureStatus === "pausing");
  return <AppShell title="Monitoreo en vivo" context="Webcam" hideContext viewport mainClassName={styles.console} pageHeader={
    <header className={styles.sessionHeader}>
      <div className={styles.sessionIdentity}>
        <Link className={styles.back} href="/" aria-label="Volver a mis análisis"><ArrowLeft size={18} aria-hidden="true" /></Link>
        <div><h1>Monitoreo en vivo</h1><p>{session ? `${session.camera.name} · ${session.name}` : "Webcam · Monitoreo local"}</p></div>
        <p role="status" className={`${styles.status} ${active ? styles.active : finalStatus === "failed" ? styles.failed : styles.paused}`}><span aria-hidden="true" />{finalStatus === "completed" ? "Análisis finalizado" : finalStatus === "failed" ? "Análisis fallido · resultados parciales" :
          finalStatus === "cancelled" ? "Análisis cancelado" : stopping ? "Finalizando" : pausing ? "Pausando" : paused ? "Análisis pausado" : captureStatus === "interrupted" ? "Captura interrumpida" : connection}</p>
      </div>
      <div className={styles.actions}>
        {finalStatus === null && <button className={styles.pauseButton} type="button"
          disabled={stopping || pausing || continuing || durable === null || (!paused && captureStatus !== "connected")}
          onClick={() => void (paused ? continueAnalysis() : pauseAnalysis())}>
          {paused ? <Play size={15} aria-hidden="true" /> : <Pause size={15} aria-hidden="true" />}
          {paused ? "Retomar análisis" : pausing ? "Pausando…" : "Pausar análisis"}</button>}
        <button className={styles.stop} type="button" disabled={stopping || finalStatus !== null || durable === null} onClick={() => void stop()}>Detener análisis</button>
        <Link className={styles.report} href={`/live/jobs/${encodeURIComponent(jobId)}/results`}>Ver reporte completo</Link></div>
    </header>
  }>
    {error && <p role="alert">{error}</p>}
    <div className={styles.layout}><section className={styles.viewer} aria-label="Vista de cámara">
    {finalStatus === null && ["interrupted", "awaiting_confirmation"].includes(captureStatus) && <section className={styles.recovery} aria-label="Recuperación de cámara">
      <h2>Revisar cámara</h2>
      <p>Los cruces anteriores se conservan. Una interrupción comienza un segmento nuevo de seguimiento.</p>
      {reconnectCheck && <>
        <div className={styles.recoveryPreview}><img alt="Encuadre para reanudar" src={`data:image/jpeg;base64,${reconnectCheck.message.image_base64}`} /></div>
        <p>Comprobación de encuadre: esta imagen no agrega detecciones ni cruces.</p>
        <label className={styles.confirmationRow} htmlFor={confirmationId}>
        <input id={confirmationId} type="checkbox" checked={confirmed} disabled={stopping || resuming || now >= reconnectCheck.expiresAt}
          onChange={(event) => setConfirmed(event.target.checked)} />
        <span>Confirmo que el encuadre coincide con la configuración</span></label>
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
      <div className={styles.camera}><div className={styles.feed}>{paused || pausing ?
        <div className={styles.feedOverlay}><Pause size={36} aria-hidden="true" /><strong>{pausing ? "Pausando análisis…" : "Análisis pausado"}</strong><span>{pausing ? "Esperando el cierre de captura y guardado de resultados" : continuing ? "Abriendo cámara para comprobar el encuadre…" : "Los conteos se conservan. Retomá cuando quieras continuar."}</span></div> : snapshot && finalStatus === null ?
        <img alt="Cámara en vivo" src={`data:image/jpeg;base64,${snapshot.image_base64}`} onLoad={() => imageLoaded(snapshot)} /> :
        <div className={styles.feedOverlay}>{finalStatus ? <><VideoOff size={36} aria-hidden="true" /><strong>Transmisión detenida</strong><span>Conexión WebSocket cerrada</span></> : <><Radio size={32} aria-hidden="true" /><span>Esperando el primer frame analizado…</span></>}</div>}
        {showHeatmap && snapshot && finalStatus === null && !paused && !pausing && samples.length > 0 && <PositionHeatmap availability="available"
          samples={samples.filter((sample) => sample.capture_timestamp_seconds <= snapshot.capture_timestamp_seconds)} />}
      </div></div>
      <div className={styles.hud}><label className={styles.heatmapControl} htmlFor={heatmapId}><Flame size={16} aria-hidden="true" /><input id={heatmapId} type="checkbox" role="switch" checked={showHeatmap}
        onChange={(event) => setShowHeatmap(event.target.checked)} /><span className={styles.switchTrack} aria-hidden="true" /><span>Superponer mapa de calor</span></label>
        <div className={styles.telemetry}><span title={paintLatency ? `Captura a pantalla estimada, incertidumbre ±${Math.ceil(paintLatency.uncertainty_ms)} ms` : "Todavía sin muestra calibrada"}><Activity size={14} aria-hidden="true" />{paused || pausing ? "Captura pausada" : paintLatency ? `${Math.round(paintLatency.estimated_ms)} ms` : "Latencia --"}</span>
          <span title={age ? `Antigüedad del frame: ${Math.round(age.estimated_ms)} ms (±${Math.ceil(age.uncertainty_ms)} ms)` : "Esperando calibración del reloj"}><Clock size={14} aria-hidden="true" />{age ? "Reloj sincronizado" : "Reloj sin calibrar"}</span><span>Sin grabación local</span></div>
      </div>
      {showHeatmap && <p className={styles.diagnostics}>Densidad de posiciones observadas durante este análisis. No representa personas únicas.</p>}
      {showHeatmap && samples.length === 0 && !sampleError && <p>Esperando posiciones guardadas…</p>}
      {showHeatmap && sampleError && <p role="alert">{sampleError}</p>}
      {stale && <p className={styles.warning}>Imagen desactualizada · los contadores corresponden al último frame mostrado.</p>}
      <p className={styles.diagnostics}>Sin grabación · los cruces cuentan pasos por la línea, no personas únicas.</p>
      <p className={styles.diagnostics}>{snapshot && <>Captura: {snapshot.capture_fps?.toFixed(1) ?? "—"} FPS · Análisis: {snapshot.analysis_fps?.toFixed(1) ?? "—"} FPS · </>}
        {age ? `Antigüedad estimada del frame: ${Math.round(age.estimated_ms)} ms (±${Math.ceil(age.uncertainty_ms)} ms)` : "Antigüedad del frame: esperando calibración del reloj"}</p>
    </section><aside className={styles.panel} aria-label="Estadísticas en vivo">
      <section><div className={styles.blockHeading}><h2>Cruces de línea</h2>
      <label className={styles.lineSelect} htmlFor={selectId}><span>Línea</span><select id={selectId} value={shopId} onChange={(event) => void selectShop(event.target.value)}>
        {shops.map((shop) => <option key={shop.shop_id} value={shop.shop_id}>{shop.shop_name}</option>)}
      </select></label></div>
      {summary ? <><dl className={styles.metrics}>
        <div><dt>{labels[0]}</dt><dd aria-label={labels[0]}>{summary.label_mode === "access" ? summary.entry_count : summary.a_to_b_count}</dd></div>
        <div><dt>{labels[1]}</dt><dd aria-label={labels[1]}>{summary.label_mode === "access" ? summary.exit_count : summary.b_to_a_count}</dd></div>
        <div><dt>Total</dt><dd aria-label="Total de cruces">{summary.total_crossings}</dd></div>
      </dl></> : <p>Configurá una línea para mostrar los cruces.</p>}</section>
      <LiveDwellSummary compact dwell={(snapshot?.zone_dwell ?? durable?.zone_dwell)?.[shopId]} />
      {summary && <CrossingChart compact minutes={minutes} summary={summary} captureStartedAt={snapshot?.capture_started_at ?? durable?.capture_started_at} />}
      <footer className={styles.panelFooter}>{!(snapshot?.coverage_complete ?? durable?.coverage_complete ?? true) && <p className={styles.warning}><AlertTriangle size={15} aria-hidden="true" />Cobertura incompleta: hubo intervalos sin analizar.</p>}
      <p className={styles.diagnostics}><Clock size={14} aria-hidden="true" />Última sincronización: {syncTime}</p></footer>
    </aside></div>
  </AppShell>;
}
