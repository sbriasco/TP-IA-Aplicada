import { useEffect, useReducer, useState, type ReactNode } from "react";

import { API_BASE_URL } from "../api/config";
import { ApiRequestError } from "../api/http";
import { createSceneVersion, getSceneVersion, listSceneVersions } from "../api/scenes";
import { getSession, referenceFrameUrl } from "../api/sessions";
import { AppShell } from "../components/AppShell";
import { Link } from "../components/Link";
import { SceneCanvas } from "../components/SceneCanvas";
import { SceneIssues } from "../components/SceneIssues";
import { SceneLayers } from "../components/SceneLayers";
import { Save, ArrowRight, ArrowLeft } from "lucide-react";
import { editorHistoryReducer } from "../editor/editorHistory";
import { createEditorState, editorReducer, toSceneVersionCreate } from "../editor/editorState";
import { addNavigationGuard } from "../navigation";
import type { SceneVersion, SceneVersionSummary } from "../types/scene";
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
  const [hidden, setHidden] = useState<ReadonlySet<string>>(new Set());
  const [configurationTitle, setConfigurationTitle] = useState(() => {
    const fallback = `Configuración ${initialVersion?.version_number ?? 1}`;
    try { return localStorage.getItem(`flowsight-scene-title:${session.camera.id}:${initialVersion?.version_number ?? "draft"}`) ?? fallback; } catch { return fallback; }
  });
  const [baseNumber, setBaseNumber] = useState(initialVersion?.version_number ?? null);
  const [saving, setSaving] = useState(false);
  const [outcome, setOutcome] = useState<SaveOutcome | null>(null);
  useEffect(() => {
    try { localStorage.setItem(`flowsight-scene-title:${session.camera.id}:${baseNumber ?? "draft"}`, configurationTitle); } catch { /* El título sigue siendo editable si el navegador bloquea el almacenamiento. */ }
  }, [configurationTitle, session.camera.id, baseNumber]);

  // FR-035: advertir al salir solo mientras haya cambios sin guardar.
  useEffect(() => {
    if (!state.isDirty && state.drawing === null) return;
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
  }, [state.isDirty, state.drawing]);

  async function handleSave() {
    setSaving(true);
    setOutcome(null);
    try {
      const payload = toSceneVersionCreate(state, session.id, frame.width, frame.height);
      const result = await createSceneVersion(apiBaseUrl, session.camera.id, payload);
      if (result.ok) {
        dispatch({ type: "saveSucceeded", version: result.version, warnings: result.warnings });
        setBaseNumber(result.version.version_number);
        setConfigurationTitle(current => /^Configuración \d+$/.test(current) ? `Configuración ${result.version.version_number}` : current);
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
          <div className="mb-2 flex flex-wrap items-center gap-3 text-xs">{backLink}<span className={styles.badge}>Paso 2: Editor de escena</span><span className="text-[var(--fs-muted)]">{frame.width} × {frame.height} px</span></div>
          <label className="sr-only" htmlFor="scene-configuration-title">Título de la configuración</label>
          <input id="scene-configuration-title" className={styles.configurationTitle} value={configurationTitle} maxLength={120} onChange={event => setConfigurationTitle(event.target.value)} aria-describedby="scene-title-help" />
          <span id="scene-title-help" className="sr-only">Título de trabajo conservado en este navegador. La configuración se guarda en el servidor con su número de versión.</span>
          <p className={styles.description}>{session.camera.name} · {baseNumber === null ? "Agregá una zona de análisis para marcar sus áreas y accesos." : `Editando la configuración ${baseNumber}. Al guardar, se crea una nueva.`}</p>
        </div>
        <div className="flex min-w-0 max-w-full flex-wrap items-center gap-2">
          {baseNumber !== null && !state.isDirty && state.drawing === null ? <Link className={styles.continueLink} href={session.source_kind === "webcam" ? `/sessions/${encodeURIComponent(session.id)}/live` : `/sessions/${encodeURIComponent(session.id)}`}>Continuar a resultados<ArrowRight size={15} aria-hidden="true" /></Link> : <button type="button" disabled title="Guardá la configuración para continuar">Continuar a resultados</button>}
        </div>
      </div>
      {state.aspectMismatch && initialVersion !== null && <p role="alert">La última versión se dibujó sobre un frame de {initialVersion.frame_width} × {initialVersion.frame_height}, con otra relación de aspecto: las figuras pueden verse deformadas. Revisalas antes de guardar.</p>}
      <fieldset className={styles.workspace} disabled={saving}>
        <section className={styles.canvasPanel} aria-label="Definí tu escena">
          <div className={styles.canvasTop}><h2>Definí tu escena</h2></div>
          <div className={styles.canvasViewport}>
            <SceneCanvas state={state} dispatch={dispatch} hidden={hidden} onGestureStart={() => dispatch({ type: "beginGesture" })} onGestureEnd={() => dispatch({ type: "endGesture" })} frameUrl={referenceFrameUrl(apiBaseUrl, frame)} />
          </div>
          <aside className={styles.guide} aria-label="Atajos del editor"><span><kbd>Esc</kbd> cancelar</span><span>Doble clic o <kbd>Enter</kbd> para cerrar polígono</span><span><kbd>← ↑ ↓ →</kbd> mover vértice · <kbd>Shift</kbd> 10 px</span></aside>
        </section>
        <aside className={styles.sidebar} aria-label="Capas y propiedades">
          <div className={styles.sidebarContent}>
          <SceneLayers state={state} dispatch={dispatch} hidden={hidden} onGestureStart={() => dispatch({ type: "beginGesture" })} onGestureEnd={() => dispatch({ type: "endGesture" })} toggleVisibility={key => setHidden(current => { const next = new Set(current); if (next.has(key)) next.delete(key); else next.add(key); return next; })} />
          {outcome?.kind === "saved" && <p role="status">Se guardó la configuración {outcome.versionNumber}.</p>}
          {outcome?.kind === "invalid" && <p role="alert">No se guardó la configuración: {outcome.count === 1 ? "hay 1 error" : `hay ${outcome.count} errores`}. Los elementos afectados están marcados en rojo; el dibujo se conserva.</p>}
          {outcome?.kind === "error" && <p role="alert">{outcome.message}</p>}
          <SceneIssues state={state} dispatch={dispatch} />
          </div>
          <div className={styles.sidebarFooter}>
          <button type="button" data-primary disabled={saving || state.drawing !== null} onClick={() => void handleSave()} className="flex items-center gap-2"><Save size={16} aria-hidden="true" />{saving ? "Guardando…" : "Guardar configuración"}</button>
          </div>
        </aside>
      </fieldset>
      <p className={styles.bottomStatus}>{state.isDirty ? "Cambios sin guardar" : baseNumber === null ? "Nueva configuración" : `Configuración ${baseNumber} guardada`} · {state.shops.length} zonas</p>
      </div>
    </AppShell>
  );
}
