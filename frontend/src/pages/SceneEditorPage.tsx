import { useEffect, useReducer, useState, type ReactNode } from "react";

import { API_BASE_URL } from "../api/config";
import { ApiRequestError } from "../api/http";
import { createSceneVersion, getSceneVersion, listSceneVersions } from "../api/scenes";
import { getSession, referenceFrameUrl } from "../api/sessions";
import { EntryLineControls } from "../components/EntryLineControls";
import { AppShell } from "../components/AppShell";
import { Link } from "../components/Link";
import { SceneCanvas } from "../components/SceneCanvas";
import { SceneIssues } from "../components/SceneIssues";
import { ShopPanel } from "../components/ShopPanel";
import { Split } from "../components/Split";
import { createEditorState, editorReducer, toSceneVersionCreate } from "../editor/editorState";
import { addNavigationGuard } from "../navigation";
import type { SceneVersion, SceneVersionSummary } from "../types/scene";
import type { ReferenceFrame, SessionDetail } from "../types/session";

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

  const backLink = <Link href={`/sessions/${encodeURIComponent(sessionId)}`}>Volver a la sesión</Link>;

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
    <AppShell title="Editor de escena">
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
  const [state, dispatch] = useReducer(editorReducer, undefined, () => {
    const initial = createEditorState({ frameWidth: frame.width, frameHeight: frame.height });
    return initialVersion === null
      ? initial
      : editorReducer(initial, { type: "loadVersion", version: initialVersion });
  });
  const [baseNumber, setBaseNumber] = useState(initialVersion?.version_number ?? null);
  const [saving, setSaving] = useState(false);
  const [outcome, setOutcome] = useState<SaveOutcome | null>(null);

  // FR-035: advertir al salir solo mientras haya cambios sin guardar.
  useEffect(() => {
    if (!state.isDirty) return;
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
  }, [state.isDirty]);

  async function handleSave() {
    setSaving(true);
    setOutcome(null);
    try {
      const payload = toSceneVersionCreate(state, session.id, frame.width, frame.height);
      const result = await createSceneVersion(apiBaseUrl, session.camera.id, payload);
      if (result.ok) {
        dispatch({ type: "saveSucceeded", version: result.version, warnings: result.warnings });
        setBaseNumber(result.version.version_number);
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
    <AppShell title={session.name} context="Editor">
      {backLink}
      <p>
        Cámara {session.camera.name} · frame {frame.width} × {frame.height}.{" "}
        {baseNumber === null
          ? `La cámara ${session.camera.name} todavía no tiene versiones de escena: agregá un local para empezar.`
          : `Editando a partir de la versión ${baseNumber}.`}
      </p>
      {state.aspectMismatch && initialVersion !== null && (
        <p role="alert">
          La última versión se dibujó sobre un frame de {initialVersion.frame_width} ×{" "}
          {initialVersion.frame_height}, con otra relación de aspecto: las figuras pueden verse deformadas.
          Revisalas antes de guardar; la versión nueva se guardará sobre el frame de esta sesión.
        </p>
      )}

      <Split
        main={
          <>
            <SceneCanvas state={state} dispatch={dispatch} frameUrl={referenceFrameUrl(apiBaseUrl, frame)} />
            <p>
              <small>
                Para dibujar, elegí un local y usá "Crear zona" o "Crear línea de entrada"; después hacé
                clic sobre el frame. Los vértices se mueven arrastrándolos o con las flechas (Shift: 10
                px) y se eliminan con Supr.
              </small>
            </p>
          </>
        }
        side={
          <>
            <ShopPanel state={state} dispatch={dispatch} />
            <EntryLineControls state={state} dispatch={dispatch} />
            <p>
              <button type="button" disabled={saving} onClick={handleSave}>
                Guardar versión
              </button>
              {state.isDirty && " Hay cambios sin guardar."}
            </p>
            {outcome?.kind === "saved" && <p role="status">Se guardó la versión {outcome.versionNumber}.</p>}
            {outcome?.kind === "invalid" && (
              <p role="alert">
                No se guardó la versión: {outcome.count === 1 ? "hay 1 error" : `hay ${outcome.count} errores`}.
                Los elementos afectados están marcados en rojo; el dibujo se conserva.
              </p>
            )}
            {outcome?.kind === "error" && <p role="alert">{outcome.message}</p>}
            <SceneIssues state={state} dispatch={dispatch} />
          </>
        }
      />
    </AppShell>
  );
}
