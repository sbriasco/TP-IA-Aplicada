/** Pruebas de `SceneIssues` (specs/004, T043): errores y advertencias que llevan al elemento. */
import { act, useReducer } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { SceneIssues } from "../src/components/SceneIssues";
import {
  createEditorState,
  editorReducer,
  type EditorAction,
  type EditorState,
} from "../src/editor/editorState";
import type { SceneIssue, SceneVersion } from "../src/types/scene";
import { click } from "./dom";

function apply(state: EditorState, ...actions: EditorAction[]): EditorState {
  return actions.reduce<EditorState>((current, action) => editorReducer(current, action), state);
}

function issue(overrides: Partial<SceneIssue>): SceneIssue {
  return {
    rule: "self_intersection",
    element: "zone:front",
    shop_index: 1,
    shop_name: "Local B",
    message: "La zona frontal se cruza a sí misma.",
    ...overrides,
  };
}

function twoShops(): EditorState {
  return apply(
    createEditorState({ frameWidth: 1280, frameHeight: 720 }),
    { type: "addShop", name: "Local A" },
    { type: "addShop", name: "Local B" },
    { type: "select", selection: null },
  );
}

describe("SceneIssues", () => {
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
    return <SceneIssues state={state} dispatch={dispatch} />;
  }

  async function render(initial: EditorState) {
    await act(async () => root.render(<Harness initial={initial} />));
  }

  function buttonContaining(text: string): HTMLButtonElement {
    const button = Array.from(container.querySelectorAll("button")).find((item) =>
      item.textContent?.includes(text),
    );
    if (button === undefined) throw new Error(`No se encontró un botón con "${text}".`);
    return button;
  }

  it("sin errores ni advertencias no muestra nada", async () => {
    await render(twoShops());

    expect(container.textContent).toBe("");
  });

  it("lista los errores con local, elemento y mensaje; activarlo selecciona el elemento", async () => {
    await render(
      apply(twoShops(), {
        type: "saveFailed",
        errors: [
          issue({}),
          issue({ element: "version", shop_index: null, shop_name: null, message: "Faltan locales." }),
        ],
      }),
    );

    expect(container.querySelector("h2")?.textContent).toBe("Errores");
    const button = buttonContaining("La zona frontal se cruza a sí misma.");
    expect(button.textContent).toBe("Local B · Zona frontal: La zona frontal se cruza a sí misma.");
    expect(container.textContent).toContain("Versión: Faltan locales.");

    await click(button);
    expect(current.selection).toEqual({ shopIndex: 1, element: "zone:front", vertexIndex: null });
  });

  it("un error de nivel local selecciona el local sin elemento", async () => {
    await render(
      apply(twoShops(), {
        type: "saveFailed",
        errors: [issue({ element: "shop", shop_index: 0, shop_name: "Local A", message: "Nombre repetido." })],
      }),
    );

    await click(buttonContaining("Nombre repetido."));
    expect(current.selection).toEqual({ shopIndex: 0, element: null, vertexIndex: null });
  });

  it("lista las advertencias del último guardado y también llevan al elemento", async () => {
    const saved: SceneVersion = {
      id: "v-2",
      camera_id: "cam-1",
      version_number: 2,
      reference_session_id: "s-1",
      frame_width: 1280,
      frame_height: 720,
      created_by_machine_id: null,
      created_at: "2026-09-28T10:00:00Z",
      shop_count: 2,
      shops: [],
    };
    await render(
      apply(twoShops(), {
        type: "saveSucceeded",
        version: saved,
        warnings: [
          issue({
            rule: "line_not_touching_zones",
            element: "entry_line",
            shop_index: 0,
            shop_name: "Local A",
            message: "La línea no toca las zonas.",
          }),
        ],
      }),
    );

    expect(container.querySelector("h2")?.textContent).toBe("Advertencias");
    await click(buttonContaining("La línea no toca las zonas."));
    expect(current.selection).toEqual({ shopIndex: 0, element: "entry_line", vertexIndex: null });
  });
});
