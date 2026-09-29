/**
 * Pruebas de `ShopPanel` (specs/004, T043): controles nativos del editor para locales y
 * elementos. Se monta con el reducer real y se verifica el estado resultante.
 */
import { act, useReducer } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { ShopPanel } from "../src/components/ShopPanel";
import {
  createEditorState,
  editorReducer,
  type EditorAction,
  type EditorState,
} from "../src/editor/editorState";
import type { SceneVersion } from "../src/types/scene";
import { byButton, byLabel, changeValue, click } from "./dom";

const FRAME_W = 1280;
const FRAME_H = 720;

function version(): SceneVersion {
  return {
    id: "v-1",
    camera_id: "cam-1",
    version_number: 1,
    reference_session_id: "s-1",
    frame_width: FRAME_W,
    frame_height: FRAME_H,
    created_by_machine_id: null,
    created_at: "2026-09-28T10:00:00Z",
    shop_count: 2,
    shops: [
      {
        shop_id: "shop-a",
        name: "Local A",
        zones: {
          front: [
            [0.125, 0.5],
            [0.375, 0.5],
            [0.375, 0.75],
            [0.125, 0.75],
          ],
        },
        entry_line: { start: [0.125, 0.875], end: [0.375, 0.875], entry_direction: "a_to_b" },
      },
      {
        shop_id: "shop-b",
        name: "Local B",
        zones: {
          interior: [
            [0.625, 0.125],
            [0.875, 0.125],
            [0.75, 0.375],
          ],
        },
        entry_line: { start: [0.625, 0.875], end: [0.875, 0.875], entry_direction: "a_to_b" },
      },
    ],
  };
}

function apply(state: EditorState, ...actions: EditorAction[]): EditorState {
  return actions.reduce<EditorState>((current, action) => editorReducer(current, action), state);
}

function empty(): EditorState {
  return createEditorState({ frameWidth: FRAME_W, frameHeight: FRAME_H });
}

function loaded(): EditorState {
  return apply(empty(), { type: "loadVersion", version: version() });
}

describe("ShopPanel", () => {
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
    return <ShopPanel state={state} dispatch={dispatch} />;
  }

  async function render(initial: EditorState) {
    await act(async () => root.render(<Harness initial={initial} />));
  }

  function optionValues(select: HTMLSelectElement): string[] {
    return Array.from(select.options).map((option) => option.value);
  }

  function optionTexts(select: HTMLSelectElement): string[] {
    return Array.from(select.options).map((option) => option.textContent ?? "");
  }

  it("agrega un local, lo selecciona y permite renombrarlo", async () => {
    await render(empty());

    await click(byButton(container, "Agregar local"));
    expect(current.shops).toHaveLength(1);
    expect(current.selection?.shopIndex).toBe(0);
    expect(byLabel<HTMLSelectElement>(container, "Local en edición").value).toBe("0");

    const name = byLabel<HTMLInputElement>(container, "Nombre del local");
    await changeValue(name, "Local A");
    expect(current.shops[0].name).toBe("Local A");
    expect(current.shops[0].shop_id).toBeNull();
    expect(optionTexts(byLabel(container, "Local en edición"))).toContain("Local A");
  });

  it("cambia de local con el select y quita solo el local elegido", async () => {
    await render(loaded());

    await changeValue(byLabel<HTMLSelectElement>(container, "Local en edición"), "1");
    expect(current.selection).toEqual({ shopIndex: 1, element: null, vertexIndex: null });
    expect(byLabel<HTMLInputElement>(container, "Nombre del local").value).toBe("Local B");

    await click(byButton(container, "Quitar local de esta versión"));
    expect(current.shops.map((shop) => shop.name)).toEqual(["Local A"]);
    expect(current.shops[0].shop_id).toBe("shop-a");
  });

  it("ofrece solo los roles disponibles y empieza a dibujar la zona elegida", async () => {
    await render(apply(loaded(), { type: "select", selection: { shopIndex: 0, element: null, vertexIndex: null } }));

    const role = byLabel<HTMLSelectElement>(container, "Rol de la zona nueva");
    expect(optionValues(role)).toEqual(["interior", "showcase"]);
    expect(optionTexts(role)).toEqual(["Interior", "Vidriera"]);

    await changeValue(role, "showcase");
    await click(byButton(container, "Crear zona"));
    expect(current.drawing).toEqual({ shopIndex: 0, element: "zone:showcase", points: [] });
  });

  it("después de crear una zona vuelve a proponer el primer rol disponible", async () => {
    await render(empty());
    await click(byButton(container, "Agregar local"));

    await changeValue(byLabel<HTMLSelectElement>(container, "Rol de la zona nueva"), "showcase");
    await click(byButton(container, "Crear zona"));
    expect(current.drawing?.element).toBe("zone:showcase");
    await click(byButton(container, "Cancelar dibujo"));

    await click(byButton(container, "Agregar local"));
    expect(byLabel<HTMLSelectElement>(container, "Rol de la zona nueva").value).toBe("front");
  });

  it("deshabilita crear zona y crear línea cuando no quedan disponibles", async () => {
    const full = apply(
      loaded(),
      { type: "select", selection: { shopIndex: 0, element: null, vertexIndex: null } },
      { type: "startDrawing", shopIndex: 0, element: "zone:interior" },
      { type: "addPoint", point: [10, 10] },
      { type: "addPoint", point: [100, 10] },
      { type: "addPoint", point: [50, 100] },
      { type: "finishDrawing" },
      { type: "startDrawing", shopIndex: 0, element: "zone:showcase" },
      { type: "addPoint", point: [200, 10] },
      { type: "addPoint", point: [300, 10] },
      { type: "addPoint", point: [250, 100] },
      { type: "finishDrawing" },
    );
    await render(full);

    expect(byButton(container, "Crear zona").disabled).toBe(true);
    expect(byButton(container, "Crear línea de entrada").disabled).toBe(true);
  });

  it("crea la línea de entrada y cierra un polígono con el botón", async () => {
    await render(empty());
    await click(byButton(container, "Agregar local"));

    await click(byButton(container, "Crear línea de entrada"));
    expect(current.drawing?.element).toBe("entry_line");
    await click(byButton(container, "Agregar vértice"));
    await click(byButton(container, "Agregar vértice"));
    expect(current.drawing).toBeNull();
    expect(current.shops[0].entry_line).not.toBeNull();

    await click(byButton(container, "Crear zona"));
    expect(current.drawing?.element).toBe("zone:front");
    const close = byButton(container, "Cerrar polígono");
    await click(byButton(container, "Agregar vértice"));
    await click(byButton(container, "Agregar vértice"));
    expect(close.disabled).toBe(true);
    await click(byButton(container, "Agregar vértice"));
    expect(byButton(container, "Cerrar polígono").disabled).toBe(false);
    await click(byButton(container, "Cerrar polígono"));
    expect(current.drawing).toBeNull();
    expect(current.shops[0].zones.front).toHaveLength(3);
    expect(current.selection).toEqual({ shopIndex: 0, element: "zone:front", vertexIndex: null });
  });

  it("cancela un dibujo en curso", async () => {
    await render(apply(loaded(), { type: "startDrawing", shopIndex: 0, element: "zone:showcase" }));

    expect(container.querySelector('[role="status"]')?.textContent).toContain("zona de vidriera");
    await click(byButton(container, "Cancelar dibujo"));
    expect(current.drawing).toBeNull();
  });

  it("elimina el vértice seleccionado sin bajar de 3", async () => {
    await render(
      apply(loaded(), {
        type: "select",
        selection: { shopIndex: 0, element: "zone:front", vertexIndex: 1 },
      }),
    );

    await click(byButton(container, "Eliminar vértice"));
    expect(current.shops[0].zones.front).toHaveLength(3);
    expect(byButton(container, "Eliminar vértice").disabled).toBe(true);
  });

  it("elige un elemento y lo elimina", async () => {
    await render(apply(loaded(), { type: "select", selection: { shopIndex: 0, element: null, vertexIndex: null } }));

    const element = byLabel<HTMLSelectElement>(container, "Elemento");
    expect(optionValues(element)).toEqual(["", "zone:front", "entry_line"]);
    await changeValue(element, "entry_line");
    expect(current.selection).toEqual({ shopIndex: 0, element: "entry_line", vertexIndex: null });

    await click(byButton(container, "Eliminar elemento"));
    expect(current.shops[0].entry_line).toBeNull();
    expect(current.selection?.element ?? null).toBeNull();
  });

  it("cambia el rol de una zona", async () => {
    await render(
      apply(loaded(), {
        type: "select",
        selection: { shopIndex: 0, element: "zone:front", vertexIndex: null },
      }),
    );

    const role = byLabel<HTMLSelectElement>(container, "Rol de la zona");
    expect(optionValues(role)).toEqual(["front", "interior", "showcase"]);
    await changeValue(role, "interior");
    expect(current.shops[0].zones.front).toBeUndefined();
    expect(current.shops[0].zones.interior).toHaveLength(4);
  });

  it("mueve el elemento a otro local ofreciendo solo destinos válidos", async () => {
    const state = apply(
      loaded(),
      { type: "addShop", name: "Local C" },
      { type: "select", selection: { shopIndex: 0, element: "zone:front", vertexIndex: null } },
    );
    await render(state);

    const target = byLabel<HTMLSelectElement>(container, "Mover a local");
    expect(optionValues(target)).toEqual(["1", "2"]);
    expect(optionTexts(target)).toEqual(["Local B", "Local C"]);
    await changeValue(target, "2");
    await click(byButton(container, "Mover elemento"));
    expect(current.shops[0].zones.front).toBeUndefined();
    expect(current.shops[2].zones.front).toHaveLength(4);
    expect(current.selection).toEqual({ shopIndex: 2, element: "zone:front", vertexIndex: null });
  });

  it("no ofrece destinos cuando todos los locales ya tienen ese elemento", async () => {
    await render(
      apply(loaded(), {
        type: "select",
        selection: { shopIndex: 0, element: "entry_line", vertexIndex: null },
      }),
    );

    expect(container.textContent).toContain("Ningún otro local puede recibir este elemento.");
    expect(Array.from(container.querySelectorAll("button")).map((b) => b.textContent)).not.toContain(
      "Mover elemento",
    );
  });
});
