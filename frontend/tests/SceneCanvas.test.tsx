/**
 * Pruebas de `SceneCanvas` (specs/004, T042).
 *
 * El canvas no guarda geometría propia: todo pasa por `editorReducer`. Las pruebas lo montan con
 * un arnés que usa el reducer real y expone el último estado. jsdom no implementa
 * `getScreenCTM`, `PointerEvent` ni `setPointerCapture`: la CTM se stubbea sobre el `<svg>` (como
 * en `editorCoordinates.test.ts`) y el arrastre se simula con `MouseEvent` de tipo `pointer*`.
 */
import { act, useReducer } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { SceneCanvas } from "../src/components/SceneCanvas";
import {
  createEditorState,
  editorReducer,
  type EditorAction,
  type EditorState,
} from "../src/editor/editorState";
import type { SceneIssue, SceneVersion } from "../src/types/scene";

const FRAME_W = 1280;
const FRAME_H = 720;
const FRAME_URL = "http://api.test/sessions/s-1/reference-frame";

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
    shop_count: 1,
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
          interior: [
            [0.125, 0.125],
            [0.375, 0.125],
            [0.25, 0.375],
          ],
        },
        // Horizontal hacia la derecha: el lado A (cross > 0) queda abajo (y mayor).
        entry_line: { start: [0.125, 0.875], end: [0.375, 0.875], entry_direction: "a_to_b" },
      },
    ],
  };
}

function apply(state: EditorState, ...actions: EditorAction[]): EditorState {
  return actions.reduce<EditorState>((current, action) => editorReducer(current, action), state);
}

function loaded(): EditorState {
  return apply(createEditorState({ frameWidth: FRAME_W, frameHeight: FRAME_H }), {
    type: "loadVersion",
    version: version(),
  });
}

// CTM de un SVG de 640×360 en (0, 0): escala 0,5 sin letterbox.
interface MatrixStub {
  a: number;
  b: number;
  c: number;
  d: number;
  e: number;
  f: number;
  inverse(): MatrixStub;
}

function matrix(a: number, b: number, c: number, d: number, e: number, f: number): MatrixStub {
  return {
    a,
    b,
    c,
    d,
    e,
    f,
    inverse() {
      const det = a * d - b * c;
      return matrix(d / det, -b / det, -c / det, a / det, (c * f - d * e) / det, (b * e - a * f) / det);
    },
  };
}

describe("SceneCanvas", () => {
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
    return <SceneCanvas state={state} dispatch={dispatch} frameUrl={FRAME_URL} />;
  }

  async function render(initial: EditorState) {
    await act(async () => root.render(<Harness initial={initial} />));
    const svg = container.querySelector("svg") as SVGSVGElement;
    (svg as unknown as { getScreenCTM: () => MatrixStub }).getScreenCTM = () =>
      matrix(0.5, 0, 0, 0.5, 0, 0);
    return svg;
  }

  function vertex(name: string): SVGCircleElement {
    const element = container.querySelector<SVGCircleElement>(`circle[aria-label="${name}"]`);
    if (element === null) throw new Error(`No se encontró "${name}".`);
    return element;
  }

  function group(name: string): SVGGElement {
    const element = container.querySelector<SVGGElement>(`g[role="group"][aria-label="${name}"]`);
    if (element === null) throw new Error(`No se encontró el grupo "${name}".`);
    return element;
  }

  async function key(target: Element, keyName: string, shiftKey = false) {
    await act(async () => {
      target.dispatchEvent(new KeyboardEvent("keydown", { key: keyName, shiftKey, bubbles: true }));
    });
  }

  async function mouse(target: Element, type: string, clientX: number, clientY: number) {
    await act(async () => {
      target.dispatchEvent(new MouseEvent(type, { clientX, clientY, bubbles: true, button: 0 }));
    });
  }

  it("dibuja el frame con viewBox en píxeles y xMidYMid meet", async () => {
    const svg = await render(loaded());

    expect(svg.getAttribute("viewBox")).toBe("0 0 1280 720");
    expect(svg.getAttribute("preserveAspectRatio")).toBe("xMidYMid meet");
    const image = svg.querySelector("image");
    expect(image?.getAttribute("href")).toBe(FRAME_URL);
    expect(image?.getAttribute("width")).toBe("1280");
    expect(image?.getAttribute("height")).toBe("720");
  });

  it("expone cada vértice como botón accesible, incluidos los extremos de la línea", async () => {
    await render(loaded());

    for (let n = 1; n <= 4; n += 1) {
      const circle = vertex(`Vértice ${n} de área externa de Local A`);
      expect(circle.getAttribute("role")).toBe("button");
      expect(circle.getAttribute("tabindex")).toBe("0");
    }
    expect(vertex("Vértice 3 de área interior de Local A")).toBeDefined();
    const start = vertex("Vértice 1 de línea de entrada de Local A");
    expect(start.getAttribute("cx")).toBe("160");
    expect(start.getAttribute("cy")).toBe("630");
    expect(vertex("Vértice 2 de línea de entrada de Local A").getAttribute("cx")).toBe("480");
    expect(container.querySelectorAll('circle[role="button"]')).toHaveLength(9);
  });

  it("distingue los roles por algo más que el color y los nombra", async () => {
    await render(loaded());

    const front = group("Área externa de Local A");
    const interior = group("Área interior de Local A");
    const frontShape = front.querySelector("polygon");
    const interiorShape = interior.querySelector("polygon");
    expect(frontShape?.getAttribute("points")).toBe("160,360 480,360 480,540 160,540");
    expect(frontShape?.getAttribute("data-role")).toBe("front");
    expect(interiorShape?.getAttribute("data-role")).toBe("interior");
    expect(frontShape?.getAttribute("stroke-dasharray") ?? "").not.toBe(
      interiorShape?.getAttribute("stroke-dasharray") ?? "",
    );
  });

  it("muestra las etiquetas A/B y la flecha de entrada según el sentido", async () => {
    await render(loaded());

    const sideA = container.querySelector('[aria-label="Lado A de Local A"]');
    const sideB = container.querySelector('[aria-label="Lado B de Local A"]');
    expect(sideA?.textContent).toBe("A");
    expect(sideB?.textContent).toBe("B");
    // Línea (160,630)→(480,630): A queda a +20 px sobre y (abajo), B a −20 px.
    expect(Number(sideA?.getAttribute("y"))).toBeGreaterThan(630);
    expect(Number(sideB?.getAttribute("y"))).toBeLessThan(630);

    const arrow = container.querySelector('[aria-label="Flecha de entrada de Local A: de A a B"]');
    const shaft = arrow?.querySelector("line");
    expect(Number(shaft?.getAttribute("y1"))).toBeGreaterThan(630);
    expect(Number(shaft?.getAttribute("y2"))).toBeLessThan(630);
  });

  it("invierte la flecha con b_to_a", async () => {
    await render(apply(loaded(), { type: "setEntryDirection", shopIndex: 0, direction: "b_to_a" }));

    expect(
      container.querySelector('[aria-label="Flecha de entrada de Local A: de B a A"]'),
    ).not.toBeNull();
  });

  it("mueve un vértice con las flechas: 1 px y 10 px con Shift", async () => {
    await render(loaded());

    await key(vertex("Vértice 1 de área externa de Local A"), "ArrowRight");
    expect(current.shops[0].zones.front?.[0]).toEqual([161, 360]);
    expect(current.isDirty).toBe(true);

    await key(vertex("Vértice 1 de área externa de Local A"), "ArrowDown", true);
    expect(current.shops[0].zones.front?.[0]).toEqual([161, 370]);
    expect(vertex("Vértice 1 de área externa de Local A").getAttribute("cy")).toBe("370");

    await key(vertex("Vértice 2 de línea de entrada de Local A"), "ArrowUp");
    expect(current.shops[0].entry_line?.end).toEqual([480, 629]);
  });

  it("selecciona el vértice al enfocarlo y lo elimina con Supr", async () => {
    await render(loaded());

    const circle = vertex("Vértice 2 de área externa de Local A");
    await act(async () => circle.dispatchEvent(new FocusEvent("focus")));
    await act(async () => circle.dispatchEvent(new FocusEvent("focusin", { bubbles: true })));
    expect(current.selection).toEqual({ shopIndex: 0, element: "zone:front", vertexIndex: 1 });

    await key(circle, "Delete");
    expect(current.shops[0].zones.front).toHaveLength(3);
  });

  it("arrastra un vértice con el puntero convirtiendo a píxeles del frame", async () => {
    await render(loaded());

    const circle = vertex("Vértice 1 de área externa de Local A");
    await mouse(circle, "pointerdown", 80, 180);
    await mouse(circle, "pointermove", 100, 200);
    await mouse(circle, "pointerup", 100, 200);
    expect(current.shops[0].zones.front?.[0]).toEqual([200, 400]);

    // Sin arrastre en curso, moverse no cambia nada.
    await mouse(circle, "pointermove", 300, 300);
    expect(current.shops[0].zones.front?.[0]).toEqual([200, 400]);
  });

  it("en modo creación, un clic sobre el fondo agrega un vértice", async () => {
    const drawing = apply(loaded(), { type: "startDrawing", shopIndex: 0, element: "zone:showcase" });
    const svg = await render(drawing);

    await mouse(svg, "click", 300, 100);
    expect(current.drawing?.points).toEqual([[600, 200]]);

    await mouse(svg, "click", 5000, -40);
    expect(current.drawing?.points).toEqual([
      [600, 200],
      [1280, 0],
    ]);
  });

  it("fuera del modo creación, un clic sobre el fondo no agrega nada", async () => {
    const svg = await render(loaded());
    const before = current;

    await mouse(svg, "click", 300, 100);
    expect(current).toBe(before);
  });

  it("Enter cierra el polígono en curso y Escape cancela", async () => {
    const drawing = apply(
      loaded(),
      { type: "startDrawing", shopIndex: 0, element: "zone:showcase" },
      { type: "addPoint", point: [600, 100] },
      { type: "addPoint", point: [700, 100] },
      { type: "addPoint", point: [650, 200] },
    );
    const svg = await render(drawing);

    await key(svg, "Enter");
    expect(current.drawing).toBeNull();
    expect(current.shops[0].zones.showcase).toHaveLength(3);
    expect(vertex("Vértice 1 de área de interés de Local A")).toBeDefined();
  });

  it("Escape descarta el dibujo en curso", async () => {
    const drawing = apply(
      loaded(),
      { type: "startDrawing", shopIndex: 0, element: "zone:showcase" },
      { type: "addPoint", point: [600, 100] },
    );
    const svg = await render(drawing);
    expect(container.querySelector('[data-drawing="true"]')).not.toBeNull();

    await key(svg, "Escape");
    expect(current.drawing).toBeNull();
    expect(container.querySelector('[data-drawing="true"]')).toBeNull();
  });

  it("resalta el elemento con error y muestra el mensaje sobre él", async () => {
    const error: SceneIssue = {
      rule: "self_intersection",
      element: "zone:front",
      shop_index: 0,
      shop_name: "Local A",
      message: "El área externa se cruza a sí misma.",
    };
    await render(apply(loaded(), { type: "saveFailed", errors: [error] }));

    const front = group("Área externa de Local A");
    expect(front.getAttribute("aria-invalid")).toBe("true");
    expect(front.textContent).toContain("El área externa se cruza a sí misma.");
    expect(group("Área interior de Local A").getAttribute("aria-invalid")).toBeNull();
  });
});
