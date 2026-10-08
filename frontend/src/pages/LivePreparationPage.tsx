import { useEffect, useId, useState } from "react";
import { ArrowLeft, Camera, Layers, Play, RefreshCw } from "lucide-react";
import { API_BASE_URL } from "../api/config";
import { checkWebcam, startWebcam } from "../api/live";
import { listSceneVersions } from "../api/scenes";
import { getSession, referenceFrameUrl } from "../api/sessions";
import { AppShell } from "../components/AppShell";
import { Link } from "../components/Link";
import { WebcamPreparationForm } from "../components/WebcamPreparationForm";
import { navigate } from "../navigation";
import type { LiveCheck } from "../types/live";
import type { SceneVersionSummary } from "../types/scene";
import type { SessionDetail } from "../types/session";
import styles from "./LivePreparationPage.module.css";

interface Props { sessionId?: string; apiBaseUrl?: string; }

export function LivePreparationPage({ sessionId, apiBaseUrl = API_BASE_URL }: Props) {
  const id = useId();
  const [session, setSession] = useState<SessionDetail | null>(null);
  const [versions, setVersions] = useState<SceneVersionSummary[]>([]);
  const [versionId, setVersionId] = useState("");
  const [check, setCheck] = useState<LiveCheck | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!sessionId) return;
    let active = true;
    getSession(apiBaseUrl, sessionId).then(async value => {
      if (value.source_kind !== "webcam") throw new Error("Esta sesión no corresponde a una webcam.");
      const loaded = await listSceneVersions(apiBaseUrl, value.camera.id);
      if (active) { setSession(value); setVersions(loaded); setVersionId(loaded[0]?.id ?? ""); }
    }).catch(reason => { if (active) setError(reason instanceof Error ? reason.message : "No se pudo cargar la sesión."); });
    return () => { active = false; };
  }, [apiBaseUrl, sessionId]);
  useEffect(() => {
    if (!check) return;
    const timer = window.setTimeout(() => { setCheck(null); setConfirmed(false); }, check.expires_in_seconds * 1000);
    return () => window.clearTimeout(timer);
  }, [check]);
  async function checkFrame() {
    if (!sessionId || busy) return;
    setBusy(true); setError(null); setCheck(null); setConfirmed(false);
    try { setCheck(await checkWebcam(apiBaseUrl, sessionId)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo comprobar el encuadre."); }
    finally { setBusy(false); }
  }
  async function start() {
    if (!sessionId || !check || !confirmed || !versionId || busy) return;
    setBusy(true); setError(null);
    try {
      const job = await startWebcam(apiBaseUrl, sessionId, versionId, check.check_token);
      navigate(`/live/jobs/${encodeURIComponent(job.id)}`);
    } catch (reason) { setCheck(null); setConfirmed(false); setError(reason instanceof Error ? reason.message : "No se pudo iniciar."); }
    finally { setBusy(false); }
  }
  const selectedVersion = versions.find(version => version.id === versionId);
  const frameSize = check ?? session?.reference_frame;
  return <AppShell title={session?.name ?? "Preparar webcam"} sessionId={sessionId} context="Detalle" subtitle={session?.camera.name} viewport={Boolean(sessionId)}
    mainClassName={sessionId === undefined ? styles.webcamMain : undefined}
    pageHeader={sessionId === undefined ? <header className={styles.webcamHeader}>
      <Link href="/" className={styles.back}><ArrowLeft size={14} aria-hidden="true" />Volver a las sesiones</Link>
      <div className={styles.webcamTitle}><h1 className="text-2xl font-bold">Preparar webcam</h1><span className={styles.badge}>1. Preparar análisis (Webcam)</span></div>
      <p>Elegí el dispositivo de captura y configurá la sesión en vivo. No se almacenará video grabado.</p>
    </header> : undefined}>
    {sessionId !== undefined && <Link href="/" className={styles.back}><ArrowLeft size={14} aria-hidden="true" />Volver a las sesiones</Link>}
    {sessionId === undefined ? <WebcamPreparationForm apiBaseUrl={apiBaseUrl} onPrepared={id => navigate(`/sessions/${encodeURIComponent(id)}/live`)} /> :
      session && <div className={styles.preparation}>
        <section className={styles.preview} aria-labelledby={id + "preview-title"}>
          <div className={styles.previewHeading}><h2 id={id + "preview-title"}>{check ? "Encuadre actual" : "Imagen de referencia"}</h2><span>{frameSize && `${frameSize.width}×${frameSize.height} · `}{busy ? "Comprobando…" : check ? "Captura actualizada" : "Referencia guardada"}</span></div>
          <div className={styles.imageArea}>
            {check ? <img className={styles.frame} src={`data:image/jpeg;base64,${check.image_base64}`} width={check.width} height={check.height} alt="Comprobación actual del encuadre de la webcam" /> :
              session.reference_frame ? <img className={styles.frame} src={referenceFrameUrl(apiBaseUrl, session.reference_frame)} width={session.reference_frame.width} height={session.reference_frame.height} alt="Imagen de referencia de la webcam" /> : <p>No hay imagen de referencia disponible.</p>}
          </div>
          <div className={styles.monitorFooter}><p className={styles.help}>{check ? "Compará esta imagen con la escena configurada antes de confirmar." : "Esta imagen se tomó al preparar la cámara. Comprobá el encuadre para obtener un frame actualizado."}</p><button type="button" disabled={busy} onClick={() => void checkFrame()}><RefreshCw size={15} aria-hidden="true" />Refrescar frame</button></div>
        </section>
        <section className={styles.settings} aria-labelledby={id + "settings-title"}>
        <h2 id={id + "settings-title"}>Preparar el análisis</h2>
        <p className={styles.help}>Definí las zonas y líneas, comprobá el encuadre y comenzá la inferencia.</p>
        <div className={styles.step}>
        {versions.length === 0 && <p className={styles.help}>Todavía no hay configuraciones. Abrí el editor para definir tus zonas y accesos.</p>}
        <div className={styles.field}><label htmlFor={id + "scene"}>Configuración de escena</label><select id={id + "scene"} disabled={busy || versions.length === 0} value={versionId} onChange={event => { setVersionId(event.target.value); setConfirmed(false); }}>
          <option value="">Elegí una configuración</option>{versions.map(version => <option key={version.id} value={version.id}>Configuración {version.version_number}</option>)}
        </select></div>
        <Link className={styles.edit} href={`/sessions/${encodeURIComponent(session.id)}/editor`}><Layers size={16} aria-hidden="true" />Editar escena / polígonos</Link>
        {selectedVersion && <p className={styles.summary}>{selectedVersion.shop_count} zonas de análisis definidas</p>}
        </div>
        <div className={styles.step}><h3>Comprobación de encuadre</h3>
        <button type="button" disabled={busy} onClick={() => void checkFrame()}><Camera size={17} aria-hidden="true" />{busy ? "Procesando…" : "Comprobar encuadre"}</button>
        {check && <label className={styles.confirm} htmlFor={id + "confirm"}>
          <input id={id + "confirm"} type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} /><span>Confirmo que este es el encuadre actual</span>
        </label>}
        </div>
        <div className={styles.start}>
        <button type="button" data-primary className="flex items-center justify-center gap-2 rounded-lg py-3 font-semibold shadow-md" disabled={busy || !check || !confirmed || !versionId} onClick={() => void start()}><Play size={18} aria-hidden="true" />Iniciar análisis en vivo</button>
        <p className={styles.help}>Sin grabación local. Los resultados medirán cruces por sentido y flujo en vivo.</p>
        {error && <p role="alert">{error}</p>}
        </div>
        </section>
      </div>}
    {error && !session && <p role="alert">{error}</p>}
    {sessionId && !session && !error && <p role="status">Cargando preparación…</p>}
  </AppShell>;
}
