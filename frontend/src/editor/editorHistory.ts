import { editorReducer, type EditorAction, type EditorState } from "./editorState";

export interface EditorHistory { present: EditorState; past: EditorState[]; future: EditorState[]; gestureStart?: EditorState }
export type HistoryAction = EditorAction | { type: "undo" } | { type: "redo" } | { type: "beginGesture" } | { type: "endGesture" };

/** Historial solo en memoria: la API continúa recibiendo el mismo EditorState. */
export function editorHistoryReducer(history: EditorHistory, action: HistoryAction): EditorHistory {
  if (action.type === "beginGesture") return history.gestureStart ? history : { ...history, gestureStart: history.present };
  if (action.type === "endGesture") {
    const { gestureStart, ...finished } = history;
    return gestureStart && gestureStart.shops !== history.present.shops ? { ...finished, past: [...history.past, gestureStart].slice(-100), future: [] } : finished;
  }
  if (action.type === "undo") {
    const previous = history.past.at(-1);
    return previous === undefined ? history : { present: previous, past: history.past.slice(0, -1), future: [history.present, ...history.future] };
  }
  if (action.type === "redo") {
    const next = history.future[0];
    return next === undefined ? history : { present: next, past: [...history.past, history.present], future: history.future.slice(1) };
  }
  const present = editorReducer(history.present, action);
  if (action.type === "saveSucceeded" || action.type === "loadVersion") return { present, past: [], future: [] };
  if (present === history.present) return history;
  if (action.type === "select" || action.type === "saveFailed") return { ...history, present };
  if (history.gestureStart) return { ...history, present };
  return { present, past: [...history.past, history.present].slice(-100), future: [] };
}
