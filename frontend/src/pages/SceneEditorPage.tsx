import { useEffect, useReducer, useState, type ReactNode } from "react";

import { API_BASE_URL } from "../api/config";
import { ApiRequestError } from "../api/http";
import { listProcessedSessions } from "../api/processedSessions";
import { createSceneVersion, getSceneVersion, listSceneVersions } from "../api/scenes";
import { getSession, referenceFrameUrl } from "../api/sessions";
import { AppShell } from "../components/AppShell";
import { Link } from "../components/Link";
import { SceneCanvas } from "../components/SceneCanvas";
import { SceneIssues } from "../components/SceneIssues";
import { SceneLayers } from "../components/SceneLayers";
import { Save, ArrowRight, ArrowLeft } from "lucide-react";
import { frameToNormalized } from "../editor/coordinates";
import { probeCrossing } from "../editor/crossingProbe";
import { editorHistoryReducer } from "../editor/editorHistory";
import { createEditorState, editorReducer, toSceneVersionCreate } from "../editor/editorState";
import { addNavigationGuard } from "../navigation";
import type { Point, SceneVersion, SceneVersionSummary } from "../types/scene";
import type { ReferenceFrame, SessionDetail } from "../types/session";
import styles from "./SceneEditorPage.module.css";

const LEAVE_MESSAGE = "Hay cambios sin guardar en la escena. ¿Salir del editor y descartarlos?";

interface SceneEditorPageProps {
  sessionId: string;
  apiBaseUrl?: string;
}

type LoadState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "no_frame"; session: SessionDetail }
  | { kind: "ready"; session: SessionDetail; frame: ReferenceFrame; version: SceneVersion | null };

function errorMessage(reason: unknown): string {
  if (!(reason instanceof ApiRequestError)) return "Ocurrió un error inesperado.";
  return reason.error.code === "not_found" ? "Sesión inexistente." : reason.error.message;
}

function versionTitle(version: { version_number?: number; display_name?: string | null } | null): string {
  return version?.display_name?.trim() || `Configuración ${version?.version_number ?? 1}`;
}

function latestVersion(versions: SceneVersionSummary[]): SceneVersionSummary | undefined {
  return versions.reduce<SceneVersionSummary | undefined>(
    (latest, version) =>
      latest === undefined || version.version_number > latest.version_number ? version : latest,
    undefined,
  );
}

async function loadEditor(apiBaseUrl: string, sessionId: string): Promise<LoadState> {
  const session = await getSession(apiBaseUrl, sessionId);
  const frame = session.reference_frame;
  if (frame === null) return { kind: "no_frame", session };
  const latest = latestVersion(await listSceneVersions(apiBaseUrl, session.camera.id));
  const version = latest === undefined ? null : await getSceneVersion(apiBaseUrl, latest.id);
  return { kind: "ready", session, frame, version };
}

/** Editor visual de escenas sobre el frame de referencia de una sesión (T044, US3). */
export function SceneEditorPage({ sessionId, apiBaseUrl = API_BASE_URL }: SceneEditorPageProps) {
  const [state, setState] = useState<LoadState>({ kind: "loading" });

  useEffect(() => {
    let active = true;
    setState({ kind: "loading" });
    loadEditor(apiBaseUrl, sessionId)
      .then((loaded) => {
        if (active) setState(loaded);
      })
      .catch((reason: unknown) => {
        if (active) setState({ kind: "error", message: errorMessage(reason) });
      });
    return () => {
      active = false;
    };
  }, [apiBaseUrl, sessionId]);

  const backLink = <Link className={styles.continueLink} href={`/sessions/${encodeURIComponent(sessionId)}`}><ArrowLeft size={15} aria-hidden="true" /><span>Volver a la sesión</span></Link>;

  if (state.kind === "ready") {
    return (
      <SceneEditor
        apiBaseUrl={apiBaseUrl}
        session={state.session}
        frame={state.frame}
        initialVersion={state.version}
        backLink={backLink}
      />
    );
  }

  return (
    <AppShell title="Editor de escena" context="Editor" sessionId={sessionId}>
      {backLink}
      {state.kind === "loading" && (
        <p role="status" data-loading="true">
          Cargando el editor…
        </p>
      )}
      {state.kind === "error" && <p role="alert">{state.message}</p>}
      {state.kind === "no_frame" && (
        <p>
          Esta sesión no tiene frame de referencia, así que no se puede abrir el editor de escena. El
          editor necesita el frame de un video registrado.
        </p>
      )}
    </AppShell>
  );
}

interface SceneEditorProps {
  apiBaseUrl: string;
  session: SessionDetail;
  frame: ReferenceFrame;
  initialVersion: SceneVersion | null;
  backLink: ReactNode;
}

type SaveOutcome =
  | { kind: "saved"; versionNumber: number }
  | { kind: "invalid"; count: number }
  | { kind: "error"; message: string };

function SceneEditor({ apiBaseUrl, session, frame, initialVersion, backLink }: SceneEditorProps) {
  const [history, dispatch] = useReducer(editorHistoryReducer, undefined, () => {
    const initial = createEditorState({ frameWidth: frame.width, frameHeight: frame.height });
    return { present: initialVersion === null ? initial : editorReducer(initial, { type: "loadVersion", version: initialVersion }), past: [], future: [] };
  });
  const state = history.present;
  const sceneContent = JSON.stringify(toSceneVersionCreate(state, session.id, frame.width, frame.height).shops);
  const [savedContent, setSavedContent] = useState(sceneContent);
  const baselineTitle = versionTitle(initialVersion);
  const [savedTitle, setSavedTitle] = useState(baselineTitle);
  const [configurationTitle, setConfigurationTitle] = useState(() => {
    if (initialVersion?.display_name?.trim()) return initialVersion.display_name.trim();
    try { return localStorage.getItem(`flowsight-scene-title:${session.camera.id}:${initialVersion?.version_number ?? "draft"}`) ?? baselineTitle; } catch { return baselineTitle; }
  });
  const hasChanges = sceneContent !== savedContent || configurationTitle.trim() !== savedTitle.trim();
  const [hidden, setHidden] = useState<ReadonlySet<string>>(new Set());
  const [probing, setProbing] = useState(false);
  const [probePoints, setProbePoints] = useState<Point[]>([]);
  const probeShop = state.shops[state.selection?.shopIndex ?? 0] ?? state.shops[0];
  const probeLine = probeShop?.entry_line ?? null;
  const probeReading = probePoints.length === 2 ? probeCrossing(
    frameToNormalized(probePoints[0], frame.width, frame.height),
    frameToNormalized(probePoints[1], frame.width, frame.height),
    probeLine ? frameToNormalized(probeLine.start, frame.width, frame.height) : null,
    probeLine ? frameToNormalized(probeLine.end, frame.width, frame.height) : null,
    probeLine?.entry_direction ?? null,
  ) : null;
  const [baseNumber, setBaseNumber] = useState(initialVersion?.version_number ?? null);
  const [saving, setSaving] = useState(false);
  const [outcome, setOutcome] = useState<SaveOutcome | null>(null);
  const [continueHref, setContinueHref] = useState<string | null>(null);
  const [resultsError, setResultsError] = useState(false);
  const [resultsCheck, setResultsCheck] = useState(0);
  useEffect(() => {
    let active = true;
    setContinueHref(null);
    setResultsError(false);
    listProcessedSessions(apiBaseUrl).then(rows => {
      if (!active) return;
      const job = rows.find(row => row.session_id === session.id);
      const path = `/sessions/${encodeURIComponent(session.id)}`;
      if (session.source_kind === "webcam") {
        setContinueHref(job && job.status !== "pending" && job.status !== "processing"
          ? `/live/jobs/${encodeURIComponent(job.job_id)}/results` : `${path}/live`);
      } else {
        setContinueHref(job?.status === "completed" && job.result_complete ? `${path}/results` : path);
      }
    }).catch(() => { if (active) setResultsError(true); });
    return () => { active = false; };
  }, [apiBaseUrl, session.id, session.source_kind, resultsCheck]);
  useEffect(() => {
    try { localStorage.setItem(`flowsight-scene-title:${session.camera.id}:${baseNumber ?? "draft"}`, configurationTitle); } catch { /* El título sigue siendo editable si el navegador bloquea el almacenamiento. */ }
  }, [configurationTitle, session.camera.id, baseNumber]);

  // FR-035: advertir al salir solo mientras haya cambios sin guardar.
  useEffect(() => {
    if (!hasChanges && state.drawing === null) return;
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    const removeGuard = addNavigationGuard(() => window.confirm(LEAVE_MESSAGE));
    return () => {
      window.removeEventListener("beforeunload", onBeforeUnload);
      removeGuard();
    };
  }, [hasChanges, state.drawing]);

  async function handleSave() {
    if (saving || !hasChanges || state.drawing !== null) return;
    setSaving(true);
    setOutcome(null);
    try {
      const payload = { ...toSceneVersionCreate(state, session.id, frame.width, frame.height), display_name: configurationTitle.trim() || null };
      const result = await createSceneVersion(apiBaseUrl, session.camera.id, payload);
      if (result.ok) {
        const savedState = editorReducer(state, { type: "saveSucceeded", version: result.version, warnings: result.warnings });
        setSavedContent(JSON.stringify(toSceneVersionCreate(savedState, session.id, frame.width, frame.height).shops));
        dispatch({ type: "saveSucceeded", version: result.version, warnings: result.warnings });
        setBaseNumber(result.version.version_number);
        const persisted = result.version.display_name?.trim() || configurationTitle.trim() || versionTitle(result.version);
        setSavedTitle(persisted);
        setConfigurationTitle(persisted);
        setOutcome({ kind: "saved", versionNumber: result.version.version_number });
      } else {
        // FR-034: los errores se marcan sobre los elementos y el dibujo se conserva.
        dispatch({ type: "saveFailed", errors: result.errors });
        setOutcome({ kind: "invalid", count: result.errors.length });
      }
    } catch (reason) {
      setOutcome({
        kind: "error",
        message: reason instanceof ApiRequestError ? reason.error.message : "Ocurrió un error inesperado.",
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <AppShell title={session.name} context="Editor" sessionId={session.id} viewport>
      <div className={`${styles.editor} h-[calc(100vh-4.5rem)] overflow-hidden`}>
      <div className={styles.workspaceHeader}>
        <div className="min-w-0">
          <div className="mb-2 flex flex-wrap items-center gap-3 text-xs">{backLink}<span className={styles.badge}>Paso 2: Editor de escena</span></div>
          <label className="sr-only" htmlFor="scene-configuration-title">Título de la configuración</label>
          <input id="scene-configuration-title" className={styles.configurationTitle} value={configurationTitle} maxLength={120} onChange={event => setConfigurationTitle(event.target.value)} aria-describedby="scene-title-help" />
          <p id="scene-title-help" className={styles.description}>{session.camera.name} · {baseNumber === null ? "Agregá una zona de análisis para marcar sus áreas y accesos." : `Editando la configuración ${baseNumber}. Al guardar, se crea una nueva.`} El nombre se guarda en el servidor con esa versión.</p>
        </div>
        <div className="flex min-w-0 max-w-full flex-wrap items-center gap-2">
          {baseNumber !== null && !hasChanges && state.drawing === null && continueHref !== null ? <Link className={styles.continueLink} href={continueHref}>Continuar a resultados<ArrowRight size={15} aria-hidden="true" /></Link> : <button type="button" disabled title={baseNumber === null || hasChanges || state.drawing !== null ? "Guardá la configuración para continuar" : "Consultando disponibilidad de resultados"}>Continuar a resultados</button>}
          {resultsError && <p role="alert">No se pudo consultar si hay resultados. <button type="button" onClick={() => setResultsCheck(current => current + 1)}>Reintentar</button></p>}
        </div>
      </div>
      {state.aspectMismatch && initialVersion !== null && <p role="alert">La última versión se dibujó sobre un frame de {initialVersion.frame_width} × {initialVersion.frame_height}, con otra relación de aspecto: las figuras pueden verse deformadas. Revisalas antes de guardar.</p>}
      <fieldset className={styles.workspace} disabled={saving}>
        <section className={styles.canvasPanel} aria-label="Definí tu escena">
          <div className={styles.canvasTop}><h2>Definí tu escena</h2></div>
          <div className={styles.canvasViewport}>
            <SceneCanvas labelMode={session.live_source?.label_mode} state={state} dispatch={dispatch} hidden={hidden} onGestureStart={() => dispatch({ type: "beginGesture" })} onGestureEnd={() => dispatch({ type: "endGesture" })} frameUrl={referenceFrameUrl(apiBaseUrl, frame)} probe={probing ? { points: probePoints, onPlace: (point) => setProbePoints((current) => current.length >= 2 ? [point] : [...current, point]) } : null} />
          </div>
          <aside className={styles.guide} aria-label="Atajos del editor"><span><kbd>Esc</kbd> cancelar</span><span>Doble clic o <kbd>Enter</kbd> para cerrar polígono</span><span><kbd>← ↑ ↓ →</kbd> mover vértice · <kbd>Shift</kbd> 10 px</span></aside>
        </section>
        <aside className={styles.sidebar} aria-label="Capas y propiedades">
          <div className={styles.sidebarContent}>
          <SceneLayers labelMode={session.live_source?.label_mode} state={state} dispatch={dispatch} hidden={hidden} onGestureStart={() => dispatch({ type: "beginGesture" })} onGestureEnd={() => dispatch({ type: "endGesture" })} toggleVisibility={key => setHidden(current => { const next = new Set(current); if (next.has(key)) next.delete(key); else next.add(key); return next; })} />
          {outcome?.kind === "saved" && <p role="status">Se guardó la configuración {outcome.versionNumber}.</p>}
          {outcome?.kind === "invalid" && <p role="alert">No se guardó la configuración: {outcome.count === 1 ? "hay 1 error" : `hay ${outcome.count} errores`}. Los elementos afectados están marcados en rojo; el dibujo se conserva.</p>}
          {outcome?.kind === "error" && <p role="alert">{outcome.message}</p>}
          <section aria-label="Prueba de cruce">
            <button type="button" aria-pressed={probing} disabled={state.drawing !== null} onClick={() => { setProbing((current) => !current); setProbePoints([]); }}>Probar cruce</button>
            {probing && <p role="status">{probeReading ? `${probeReading.label}. ${probeReading.detail}` : "Hacé dos clics sobre el frame: primero los pies de un lado de la línea y después del otro."}</p>}
          </section>
          <SceneIssues state={state} dispatch={dispatch} />
          </div>
          <div className={styles.sidebarFooter}>
          <button type="button" data-primary disabled={saving || !hasChanges || state.drawing !== null} title={!hasChanges ? "No hay cambios para guardar" : undefined} onClick={() => void handleSave()} className="flex items-center gap-2"><Save size={16} aria-hidden="true" />{saving ? "Guardando…" : "Guardar configuración"}</button>
          </div>
        </aside>
      </fieldset>
      <p className={styles.bottomStatus}>{hasChanges ? "Cambios sin guardar" : baseNumber === null ? "Nueva configuración" : `Configuración ${baseNumber} guardada`} · {state.shops.length} zonas</p>
      </div>
    </AppShell>
  );
}
