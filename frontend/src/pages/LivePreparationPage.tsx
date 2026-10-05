import { useEffect, useId, useState } from "react";
import { API_BASE_URL } from "../api/config";
import { checkWebcam, startWebcam } from "../api/live";
import { listSceneVersions } from "../api/scenes";
import { getSession } from "../api/sessions";
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
  return <AppShell title={session?.name ?? "Preparar webcam"}>
    <Link href="/">Volver a las sesiones</Link>
    {sessionId === undefined ? <WebcamPreparationForm apiBaseUrl={apiBaseUrl} onPrepared={id => navigate(`/sessions/${encodeURIComponent(id)}/live`)} /> :
      session && <div className={styles.preparation}>
        <p>Sin grabación. Los resultados medirán cruces por sentido, no visitas únicas.</p>
        <Link href={`/sessions/${encodeURIComponent(session.id)}/editor`}>Configurar escena</Link>
        <label htmlFor={id + "scene"}>Configuración</label><select id={id + "scene"} value={versionId} onChange={event => { setVersionId(event.target.value); setConfirmed(false); }}>
          <option value="">Elegí una configuración</option>{versions.map(version => <option key={version.id} value={version.id}>Configuración {version.version_number}</option>)}
        </select>
        <button type="button" disabled={busy} onClick={() => void checkFrame()}>Comprobar encuadre</button>
        {check && <>
          <img className={styles.frame} src={`data:image/jpeg;base64,${check.image_base64}`} width={check.width} height={check.height} alt="Comprobación actual del encuadre de la webcam" />
          <input id={id + "confirm"} type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} /><label htmlFor={id + "confirm"}>Confirmo que este es el encuadre actual</label>
        </>}
        <button type="button" disabled={busy || !check || !confirmed || !versionId} onClick={() => void start()}>Iniciar en vivo</button>
      </div>}
    {error && <p role="alert">{error}</p>}
    {sessionId && !session && !error && <p role="status">Cargando preparación…</p>}
  </AppShell>;
}
