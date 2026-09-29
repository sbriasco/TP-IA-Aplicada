/** Pruebas de `EntryLineControls` (specs/004, T043): sentido de entrada con radios nativos. */
import { act, useReducer } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { EntryLineControls } from "../src/components/EntryLineControls";
import {
  createEditorState,
  editorReducer,
  type EditorAction,
  type EditorState,
} from "../src/editor/editorState";
import { byLabel, click } from "./dom";

function apply(state: EditorState, ...actions: EditorAction[]): EditorState {
  return actions.reduce<EditorState>((current, action) => editorReducer(current, action), state);
}

function withLine(): EditorState {
  return apply(
    createEditorState({ frameWidth: 1280, frameHeight: 720 }),
    { type: "addShop", name: "Local A" },
    { type: "startDrawing", shopIndex: 0, element: "entry_line" },
    { type: "addPoint", point: [100, 600] },
    { type: "addPoint", point: [400, 600] },
  );
}

describe("EntryLineControls", () => {
  let container: HTMLDivElement;
  let root: Root;
  let current: EditorState;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
  });

  function Harness({ initial }: { initial: EditorState }) {
    const [state, dispatch] = useReducer(editorReducer, initial);
    current = state;
    return <EntryLineControls state={state} dispatch={dispatch} />;
  }

  async function render(initial: EditorState) {
    await act(async () => root.render(<Harness initial={initial} />));
  }

  it("agrupa los radios en un fieldset con legend y marca el sentido actual", async () => {
    await render(withLine());

    const fieldset = container.querySelector("fieldset");
    expect(fieldset?.querySelector("legend")?.textContent).toBe("Sentido de entrada de Local A");
    const aToB = byLabel<HTMLInputElement>(container, "A → B es entrada");
    const bToA = byLabel<HTMLInputElement>(container, "B → A es entrada");
    expect(aToB.type).toBe("radio");
    expect(aToB.name).toBe(bToA.name);
    expect(aToB.checked).toBe(true);
    expect(bToA.checked).toBe(false);
  });

  it("cambia el sentido de entrada", async () => {
    await render(withLine());

    await click(byLabel<HTMLInputElement>(container, "B → A es entrada"));
    expect(current.shops[0].entry_line?.entry_direction).toBe("b_to_a");
    expect(byLabel<HTMLInputElement>(container, "B → A es entrada").checked).toBe(true);

    await click(byLabel<HTMLInputElement>(container, "A → B es entrada"));
    expect(current.shops[0].entry_line?.entry_direction).toBe("a_to_b");
  });

  it("sin línea de entrada deshabilita los radios y lo explica", async () => {
    await render(
      apply(createEditorState({ frameWidth: 1280, frameHeight: 720 }), {
        type: "addShop",
        name: "Local A",
      }),
    );

    expect(container.querySelector("fieldset")?.disabled).toBe(true);
    expect(container.textContent).toContain("Local A todavía no tiene línea de entrada.");
  });

  it("sin local seleccionado no muestra nada", async () => {
    await render(createEditorState({ frameWidth: 1280, frameHeight: 720 }));

    expect(container.querySelector("fieldset")).toBeNull();
  });
});
