import type { Dispatch } from "react";
import { MousePointer, Hexagon, Spline, Undo2, Redo2, Trash2 } from "lucide-react";
import { availableZoneRoles, type EditorAction, type EditorState } from "../editor/editorState";

interface SceneEditorToolbarProps {
  state: EditorState;
  dispatch: Dispatch<EditorAction>;
  canUndo: boolean;
  canRedo: boolean;
  undo: () => void;
  redo: () => void;
}

export function SceneEditorToolbar({ state, dispatch, canUndo, canRedo, undo, redo }: SceneEditorToolbarProps) {
  const index = state.selection?.shopIndex;
  const role = index === undefined ? undefined : availableZoneRoles(state, index)[0];
  const lineAvailable = index !== undefined && state.shops[index]?.entry_line === null;
  const buttonClass = "!min-h-9 !p-2 flex items-center justify-center gap-2 !text-xs";
  return <div role="toolbar" aria-label="Herramientas de escena" className="flex flex-wrap items-center justify-center gap-1 rounded-lg border border-[var(--fs-line)] bg-[var(--fs-surface)] p-1">
    <button type="button" title="Seleccionar y mover vértices" aria-label="Seleccionar y mover" aria-pressed={state.drawing === null} className={buttonClass} onClick={() => dispatch({ type: "cancelDrawing" })}><MousePointer size={17} aria-hidden="true" /></button>
    <button type="button" aria-label="Área" title="Dibujar polígono / Área" className={buttonClass} disabled={role === undefined} aria-pressed={state.drawing?.element.startsWith("zone:") ?? false} onClick={() => { if (index !== undefined && role) dispatch({ type: "startDrawing", shopIndex: index, element: `zone:${role}` }); }}><Hexagon size={17} aria-hidden="true" /><span className="hidden sm:inline">Área</span></button>
    <button type="button" aria-label="Línea de cruce" title="Línea de cruce" className={buttonClass} disabled={!lineAvailable} aria-pressed={state.drawing?.element === "entry_line"} onClick={() => { if (index !== undefined) dispatch({ type: "startDrawing", shopIndex: index, element: "entry_line" }); }}><Spline size={17} aria-hidden="true" /><span className="hidden sm:inline">Línea de cruce</span></button>
    <span className="mx-1 h-5 border-l border-[var(--fs-line)]" aria-hidden="true" />
    <button type="button" className={buttonClass} aria-label="Deshacer" title="Deshacer" disabled={!canUndo} onClick={undo}><Undo2 size={17} aria-hidden="true" /></button>
    <button type="button" className={buttonClass} aria-label="Rehacer" title="Rehacer" disabled={!canRedo} onClick={redo}><Redo2 size={17} aria-hidden="true" /></button>
    <button type="button" className={buttonClass} aria-label="Limpiar puntos" title="Limpiar los puntos del dibujo en curso" disabled={state.drawing === null || state.drawing.points.length === 0} onClick={() => { if (state.drawing) dispatch({ type: "startDrawing", shopIndex: state.drawing.shopIndex, element: state.drawing.element }); }}><Trash2 size={17} aria-hidden="true" /></button>
  </div>;
}
