import { useEffect, useId, useState } from "react";
import { Camera, Plus, Search, Trash2, Video } from "lucide-react";
import { API_BASE_URL } from "../api/config";
import { ApiRequestError } from "../api/http";
import { listProcessedSessions, type ProcessedSession } from "../api/processedSessions";
import { deleteSession, listSessions } from "../api/sessions";
import { AppShell } from "../components/AppShell";
import { CameraManager } from "../components/CameraManager";
import { DashboardSteps } from "../components/DashboardSteps";
import { Link } from "../components/Link";
import { Modal } from "../components/Modal";
import { VideoUploadForm } from "../components/VideoUploadForm";
import { navigate } from "../navigation";
import type { SessionSummary } from "../types/session";
import type { AnalysisStatus } from "../types/analysis";
import { analysisDuration, analysisItem } from "../presentation/analysis";
import styles from "./SessionsPage.module.css";

const STATUS: Record<AnalysisStatus, string> = {
  unanalysed: "Sin analizar", loading: "Cargando estado…", unavailable: "Estado no disponible", incomplete: "Resultado incompleto",
  pending: "En cola", processing: "Analizando", completed: "Resultados listos",
  failed: "Error en el análisis", cancelled: "Cancelado",
};
function message(reason: unknown): string {
  return reason instanceof ApiRequestError ? reason.error.message : "No se pudo completar la operación.";
}
interface SessionsPageProps { apiBaseUrl?: string; }

export function SessionsPage({ apiBaseUrl = API_BASE_URL }: SessionsPageProps) {
  const searchId = useId();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<"all" | "active" | "completed">("all");
  const [sessions, setSessions] = useState<SessionSummary[] | null>(null);
  const [jobs, setJobs] = useState<ProcessedSession[]>([]);
  const [jobsLoaded, setJobsLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [jobsError, setJobsError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [videoBusy, setVideoBusy] = useState(false);
  const [managingCameras, setManagingCameras] = useState(false);
  const [cameraBusy, setCameraBusy] = useState(false);
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
  const items = (sessions ?? []).map(session => analysisItem(session, jobsBySession.get(session.id), jobsLoaded, jobsError !== null));
  const needle = query.trim().toLocaleLowerCase("es-AR");
  const visible = items.filter(item => (filter === "all" || (filter === "active" ? item.busy : item.status === "completed" || item.status === "incomplete")) &&
    `${item.session.name} ${item.session.camera.name}`.toLocaleLowerCase("es-AR").includes(needle));
  const editable = sessions?.find(session => session.source_kind !== "synthetic");

  return (
    <AppShell title="Tus análisis" subtitle="Cargá un video, configurá la escena y consultá lo que sucede en tu espacio." actions={
      <div className={styles.headingActions}><Link href="/live" className={styles.outlineAction}><Video size={16} aria-hidden="true" />Webcam en vivo</Link><button type="button" onClick={() => setManagingCameras(true)}><Camera size={16} aria-hidden="true" />Cámaras</button><button type="button" data-primary onClick={() => setUploading(true)}><Plus size={18} aria-hidden="true" />Nuevo análisis</button></div>
    }>
      <DashboardSteps onUpload={() => setUploading(true)} configureHref={editable ? `/sessions/${encodeURIComponent(editable.id)}/editor` : undefined} resultsHref={items.find(item => item.ready)?.href} />
      {error && <p role="alert">{error}</p>}
      {jobsError && <p role="alert">No se pudieron cargar los estados. {jobsError}</p>}
      {notice && <p role="status">{notice}</p>}
      {sessions === null && !error && <p role="status">Cargando análisis…</p>}
      {sessions?.length === 0 && <div className={styles.empty}><h2>Todavía no hay análisis.</h2><p>Empezá con un video. Después podrás definir qué querés medir.</p><button type="button" onClick={() => setUploading(true)}>Cargar mi primer video</button></div>}
      {sessions !== null && sessions.length > 0 && (
        <section className={styles.history} aria-label="Historial de análisis">
          <div className={styles.tableHeading}><div className={styles.tableTitle}><h2>Videos y análisis</h2><span>{sessions.length} en el historial</span></div>
            <div className={styles.tableControls}>
              <div className={styles.search}><label htmlFor={searchId} className={styles.srOnly}>Buscar análisis</label><Search size={15} aria-hidden="true" /><input id={searchId} type="search" placeholder="Buscar video…" value={query} onChange={event => setQuery(event.target.value)} /></div>
              <div className={styles.filters} role="group" aria-label="Filtrar análisis por estado">
                <button type="button" aria-pressed={filter === "all"} onClick={() => setFilter("all")}>Todos</button>
                <button type="button" aria-pressed={filter === "active"} onClick={() => setFilter("active")}>Activos</button>
                <button type="button" aria-pressed={filter === "completed"} onClick={() => setFilter("completed")}>Completados</button>
              </div>
            </div>
          </div>
          <div className={styles.tableScroll} role="region" aria-label="Tabla de análisis" tabIndex={0}>
            <table><thead><tr><th scope="col">Video / análisis</th><th scope="col">Cámara</th><th scope="col">Estado</th><th scope="col">Creado</th><th scope="col" className={styles.actionCell}>Acciones</th></tr></thead>
              <tbody>{visible.map(({ session, busy, ready, status, href, action, durationSeconds }) => {
                const path = "/sessions/" + encodeURIComponent(session.id);
                const live = session.source_kind === "webcam";
                return <tr key={session.id}>
                  <td><Link href={path}>{session.name}</Link><small className={styles.duration}>Tiempo analizado: {analysisDuration(durationSeconds)}</small></td><td><span className={styles.cameraName}><Video size={14} aria-hidden="true" />{session.camera.name}</span></td>
                  <td><span className={ready ? styles.ready : busy ? styles.running : status === "failed" ? styles.failed : styles.status}>{ready && <span className={styles.dot} aria-hidden="true" />}{STATUS[status]}</span>{session.source_kind === "synthetic" && <small className={styles.synthetic}>Datos sintéticos</small>}{live && <small className={styles.synthetic}>Webcam · Sin grabación</small>}</td>
                  <td><time dateTime={session.created_at}>{new Date(session.created_at).toLocaleDateString("es-AR", { day: "numeric", month: "short" })}</time></td>
                  <td className={styles.actionCell}><div className={styles.rowActions}><Link className={styles.openAction} href={href}>{action}</Link>
                  <button className={styles.deleteButton} type="button" aria-label={"Eliminar " + session.name} disabled={busy} title={busy ? "Esperá a que termine o cancelá el análisis antes de eliminarlo" : "Eliminar del historial"} onClick={() => { setSelected(session); setRemoveError(null); }}>
                    <Trash2 size={16} aria-hidden="true" />
                  </button></div></td>
                </tr>;
              })}{visible.length === 0 && <tr><td colSpan={5} className={styles.noMatches}>No hay análisis que coincidan con la búsqueda y el filtro.</td></tr>}</tbody>
            </table>
          </div>
        </section>
      )}
      {uploading && <Modal title="Nuevo análisis" subtitle="Cargá el video de tu cámara fija y asigná la ubicación para comenzar." wide busy={videoBusy} onClose={() => setUploading(false)}><VideoUploadForm apiBaseUrl={apiBaseUrl} onCancel={() => setUploading(false)} onBusyChange={setVideoBusy} onRegistered={(session) => navigate("/sessions/" + encodeURIComponent(session.id))} /></Modal>}
      {managingCameras && <Modal title="Administrar cámaras" busy={cameraBusy} onClose={() => setManagingCameras(false)}>
        <CameraManager apiBaseUrl={apiBaseUrl} onBusyChange={setCameraBusy} onRenamed={(camera) => {
          setSessions((current) => current?.map((session) => session.camera.id === camera.id ? { ...session, camera } : session) ?? null);
        }} />
      </Modal>}
      {selected && <Modal title="Eliminar análisis" busy={removing} onClose={() => setSelected(null)}>
        <p>¿Eliminar <strong>{selected.name}</strong> del historial?</p>
        <p className={styles.help}>No volverá a aparecer en la lista. Se conservan los archivos y las referencias de escena que puedan usar otros análisis.</p>
        {removeError && <p role="alert">{removeError}</p>}
        <div className={styles.confirm}><button type="button" disabled={removing} onClick={() => setSelected(null)}>Cancelar</button><button type="button" className={styles.danger} disabled={removing} onClick={() => void remove()}>{removing ? "Eliminando…" : "Eliminar del historial"}</button></div>
      </Modal>}
    </AppShell>
  );
}
