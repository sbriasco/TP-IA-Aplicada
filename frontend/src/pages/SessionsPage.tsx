import { useEffect, useState } from "react";
import { API_BASE_URL } from "../api/config";
import { ApiRequestError } from "../api/http";
import { listProcessedSessions, type ProcessedSession } from "../api/processedSessions";
import { deleteSession, listSessions } from "../api/sessions";
import { AppShell } from "../components/AppShell";
import { Link } from "../components/Link";
import { Modal } from "../components/Modal";
import { VideoUploadForm } from "../components/VideoUploadForm";
import { navigate } from "../navigation";
import type { SessionSummary } from "../types/session";
import styles from "./SessionsPage.module.css";

const STATUS: Record<ProcessedSession["status"], string> = {
  pending: "En cola", processing: "Analizando", completed: "Resultados listos",
  failed: "Error en el análisis", cancelled: "Cancelado",
};
function message(reason: unknown): string {
  return reason instanceof ApiRequestError ? reason.error.message : "No se pudo completar la operación.";
}
interface SessionsPageProps { apiBaseUrl?: string; }

export function SessionsPage({ apiBaseUrl = API_BASE_URL }: SessionsPageProps) {
  const [sessions, setSessions] = useState<SessionSummary[] | null>(null);
  const [jobs, setJobs] = useState<ProcessedSession[]>([]);
  const [jobsLoaded, setJobsLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [jobsError, setJobsError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [selected, setSelected] = useState<SessionSummary | null>(null);
  const [removing, setRemoving] = useState(false);
  const [removeError, setRemoveError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setSessions(null);
    setError(null);
    setJobs([]);
    setJobsError(null);
    setJobsLoaded(false);
    void Promise.allSettled([
      listSessions(apiBaseUrl).then((list) => { if (active) setSessions(list); }, (reason: unknown) => { if (active) setError(message(reason)); }),
      listProcessedSessions(apiBaseUrl).then((history) => { if (active) { setJobs(history); setJobsLoaded(true); } }, (reason: unknown) => { if (active) { setJobsError(message(reason)); setJobsLoaded(true); } }),
    ]);
    return () => { active = false; };
  }, [apiBaseUrl]);

  async function remove() {
    if (!selected || removing) return;
    setRemoving(true);
    setRemoveError(null);
    try {
      await deleteSession(apiBaseUrl, selected.id);
      setSessions((current) => current?.filter((item) => item.id !== selected.id) ?? null);
      setNotice("Se eliminó «" + selected.name + "» del historial.");
      setSelected(null);
    } catch (reason) { setRemoveError(message(reason)); }
    finally { setRemoving(false); }
  }
  const jobsBySession = new Map(jobs.map((job) => [job.session_id, job]));

  return (
    <AppShell title="Tus análisis">
      <div className={styles.heading}>
        <p>Cargá un video, configurá la escena y consultá lo que sucede en tu espacio.</p>
        <button type="button" data-primary onClick={() => setUploading(true)}>Nuevo análisis</button>
      </div>
      <ol className={styles.steps} aria-label="Cómo funciona FlowSight">
        <li><span>1</span><div><strong>Cargá un video</strong><small>De una cámara fija</small></div></li>
        <li><span>2</span><div><strong>Configurá la escena</strong><small>Dibujá locales, zonas y accesos</small></div></li>
        <li><span>3</span><div><strong>Analizá y consultá</strong><small>Resultados y agente de IA</small></div></li>
      </ol>
      {error && <p role="alert">{error}</p>}
      {jobsError && <p role="alert">No se pudieron cargar los estados. {jobsError}</p>}
      {notice && <p role="status">{notice}</p>}
      {sessions === null && !error && <p role="status">Cargando análisis…</p>}
      {sessions?.length === 0 && <div className={styles.empty}><h2>Todavía no hay análisis.</h2><p>Empezá con un video. Después podrás definir qué querés medir.</p><button type="button" onClick={() => setUploading(true)}>Cargar mi primer video</button></div>}
      {sessions !== null && sessions.length > 0 && (
        <section className={styles.history} aria-label="Historial de análisis">
          <div className={styles.tableHeading}><h2>Videos y análisis</h2><span>{sessions.length} en el historial</span></div>
          <div className={styles.tableScroll} role="region" aria-label="Tabla de análisis" tabIndex={0}>
            <table><thead><tr><th scope="col">Video / análisis</th><th scope="col">Cámara</th><th scope="col">Estado</th><th scope="col">Creado</th><th scope="col" className={styles.actionCell}>Acciones</th><th scope="col" className={styles.deleteCell} aria-label="Eliminar análisis" /></tr></thead>
              <tbody>{sessions.map((session) => {
                const job = jobsBySession.get(session.id);
                const busy = job?.status === "pending" || job?.status === "processing";
                const ready = job?.status === "completed" && job.result_complete;
                const path = "/sessions/" + encodeURIComponent(session.id);
                const target = busy ? "/?job=" + encodeURIComponent(job.job_id) : ready ? path + "/results" : path;
                const action = busy ? "Ver avance" : ready ? "Ver resultados" : "Continuar";
                const status = !jobsLoaded ? "Cargando estado…" : jobsError ? "Estado no disponible" : !job ? "Sin analizar" : job.status === "completed" && !job.result_complete ? "Resultado incompleto" : STATUS[job.status];
                return <tr key={session.id}>
                  <td><Link href={path}>{session.name}</Link></td><td>{session.camera.name}</td>
                  <td><span className={ready ? styles.ready : busy ? styles.running : styles.status}>{status}</span>{session.source_kind === "synthetic" && <small className={styles.synthetic}>Datos sintéticos</small>}</td>
                  <td><time dateTime={session.created_at}>{new Date(session.created_at).toLocaleDateString("es-AR", { day: "numeric", month: "short" })}</time></td>
                  <td className={styles.actionCell}><Link className={styles.openAction} href={target}>{action}</Link></td>
                  <td className={styles.deleteCell}><button className={styles.deleteButton} type="button" aria-label={"Eliminar " + session.name} disabled={busy} title={busy ? "Esperá a que termine o cancelá el análisis antes de eliminarlo" : "Eliminar del historial"} onClick={() => { setSelected(session); setRemoveError(null); }}>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false"><path d="M3 6h18M9 6V4h6v2M5 6l1 14h12l1-14M10 10v6M14 10v6" /></svg>
                  </button></td>
                </tr>;
              })}</tbody>
            </table>
          </div>
          <aside className={styles.legend} aria-label="Guía de estados">
            <div className={styles.legendTitle}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="9" /><path d="M12 11v6M12 7h.01" /></svg>
              <span>Guía de estados</span>
            </div>
            <dl className={styles.legendStates}>
              <div><dt><span className={styles.status}>Sin analizar</span></dt><dd>Video cargado. Configurá la escena para empezar.</dd></div>
              <div><dt><span className={styles.ready}>Resultados listos</span></dt><dd>Análisis completo. Explorá las métricas y consultá al agente.</dd></div>
            </dl>
          </aside>
        </section>
      )}
      {uploading && <Modal title="Nuevo análisis" onClose={() => setUploading(false)}><VideoUploadForm apiBaseUrl={apiBaseUrl} onRegistered={(session) => navigate("/sessions/" + encodeURIComponent(session.id))} /></Modal>}
      {selected && <Modal title="Eliminar análisis" busy={removing} onClose={() => setSelected(null)}>
        <p>¿Eliminar <strong>{selected.name}</strong> del historial?</p>
        <p className={styles.help}>No volverá a aparecer en la lista. Se conservan los archivos y las referencias de escena que puedan usar otros análisis.</p>
        {removeError && <p role="alert">{removeError}</p>}
        <div className={styles.confirm}><button type="button" disabled={removing} onClick={() => setSelected(null)}>Cancelar</button><button type="button" className={styles.danger} disabled={removing} onClick={() => void remove()}>{removing ? "Eliminando…" : "Eliminar del historial"}</button></div>
      </Modal>}
    </AppShell>
  );
}
