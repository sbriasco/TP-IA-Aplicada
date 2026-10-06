import { describe, expect, it } from "vitest";
import { createEditorState, toSceneVersionCreate } from "../src/editor/editorState";
import { editorHistoryReducer } from "../src/editor/editorHistory";

describe("historial del editor", () => {
  it("agrupa más de cien movimientos de un arrastre en una operación", () => {
    let history = { present: createEditorState({ frameWidth: 1000, frameHeight: 1000 }), past: [], future: [] } as Parameters<typeof editorHistoryReducer>[0];
    history = editorHistoryReducer(history, { type: "addShop", name: "Acceso" });
    history = editorHistoryReducer(history, { type: "startDrawing", shopIndex: 0, element: "zone:front" });
    for (const point of [[10, 10], [800, 10], [800, 800]] as [number, number][]) history = editorHistoryReducer(history, { type: "addPoint", point });
    history = editorHistoryReducer(history, { type: "finishDrawing" });
    const count = history.past.length;
    history = editorHistoryReducer(history, { type: "beginGesture" });
    for (let x = 11; x < 200; x++) history = editorHistoryReducer(history, { type: "moveVertex", shopIndex: 0, element: "zone:front", vertexIndex: 0, point: [x, 10] });
    history = editorHistoryReducer(history, { type: "endGesture" });
    expect(history.past).toHaveLength(count + 1);
    history = editorHistoryReducer(history, { type: "undo" });
    expect(history.present.shops[0]?.zones.front?.[0]).toEqual([10, 10]);
    history = editorHistoryReducer(history, { type: "redo" });
    expect(history.present.shops[0]?.zones.front?.[0]).toEqual([199, 10]);
  });
  it("deshace y rehace geometría sin cambiar el contrato normalizado", () => {
    let history = { present: createEditorState({ frameWidth: 100, frameHeight: 100 }), past: [], future: [] } as Parameters<typeof editorHistoryReducer>[0];
    history = editorHistoryReducer(history, { type: "addShop", name: "Acceso" });
    history = editorHistoryReducer(history, { type: "startDrawing", shopIndex: 0, element: "zone:front" });
    for (const point of [[10, 10], [80, 10], [80, 80]] as [number, number][]) history = editorHistoryReducer(history, { type: "addPoint", point });
    history = editorHistoryReducer(history, { type: "finishDrawing" });
    const payload = toSceneVersionCreate(history.present, "s-1", 100, 100);
    history = editorHistoryReducer(history, { type: "undo" });
    expect(history.present.shops[0]?.zones.front).toBeUndefined();
    expect(history.present.drawing?.points).toHaveLength(3);
    history = editorHistoryReducer(history, { type: "redo" });
    expect(toSceneVersionCreate(history.present, "s-1", 100, 100)).toEqual(payload);
    history = editorHistoryReducer(history, { type: "undo" });
    history = editorHistoryReducer(history, { type: "cancelDrawing" });
    expect(history.future).toHaveLength(0);
  });
});
