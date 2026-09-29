/**
 * Pruebas del reducer del editor de escenas (specs/004, T038 → T041).
 *
 * Contrato que asumen para `src/editor/editorState.ts` (reducer puro para `useReducer`, sin DOM):
 *
 * Exportaciones
 * - `createEditorState({ frameWidth, frameHeight }): EditorState` — estado inicial vacío sobre el
 *   frame de referencia de la sesión. Pensado para `useReducer(editorReducer, frame, createEditorState)`.
 * - `editorReducer(state, action): EditorState` — puro. Una acción que no aplica (índice
 *   inexistente, regla violada, sin dibujo en curso…) devuelve el MISMO objeto `state` (`toBe`),
 *   así React no re-renderiza y la UI puede despachar sin validar antes.
 * - `toSceneVersionCreate(state, referenceSessionId, frameWidth, frameHeight): SceneVersionCreate`
 *   — única función que normaliza (con `frameToNormalized` de `coordinates.ts`, 6 decimales). No
 *   modifica `state`.
 * - Selectores: `issuesFor(state, shopIndex, element?)`, `hasIssue(state, shopIndex, element)`,
 *   `availableZoneRoles(state, shopIndex)`.
 * - Tipos: `EditorState`, `EditorShop`, `EditorElement`, `EditorSelection`, `EditorDrawing`,
 *   `EditorAction`.
 *
 * Forma del estado (todas las coordenadas en PÍXELES DEL FRAME de la sesión, nunca normalizadas)
 * - `frameWidth`, `frameHeight`: tamaño del frame de referencia de la sesión; se usan para
 *   convertir al cargar y para limitar (`clampToFrame`) todo punto que entra al estado.
 * - `baseVersionId: string | null`: versión cargada (o la última guardada); `null` si no hay.
 * - `shops: EditorShop[]`: en el orden de la request; el índice en este arreglo ES el `shop_index`
 *   de los errores de la API. `EditorShop = { key, shop_id, name, zones, entry_line }`:
 *   - `key: string` estable y único dentro del editor (para `key` de React; no se envía);
 *   - `shop_id: string | null` (`null` = local nuevo);
 *   - `zones: Partial<Record<ZoneRole, Point[]>>` y `entry_line: EntryLine | null`, en píxeles.
 * - `selection: EditorSelection | null` con
 *   `EditorSelection = { shopIndex: number; element: EditorElement | null; vertexIndex: number | null }`.
 *   En una línea, `vertexIndex` 0 = `start` y 1 = `end`.
 * - `drawing: EditorDrawing | null` con `EditorDrawing = { shopIndex; element; points: Point[] }`:
 *   el polígono o la línea a medio dibujar, para que el canvas lo muestre como vista previa.
 * - `isDirty: boolean`, `aspectMismatch: boolean`.
 * - `issues: SceneIssue[]` (errores del último 422) y `warnings: SceneIssue[]` (advertencias del
 *   último guardado exitoso).
 *
 * `EditorElement = "zone:front" | "zone:interior" | "zone:showcase" | "entry_line"`: los mismos
 * valores que `SceneIssueElement` usa para zonas y línea, así un error se mapea sin traducción.
 *
 * Acciones (`EditorAction`, unión discriminada por `type`)
 * - `{ type: "loadVersion", version: SceneVersion }` — normalizado × frame DE LA SESIÓN
 *   (`normalizedToFrame(p, state.frameWidth, state.frameHeight)`), conserva `shop_id` y el orden;
 *   `baseVersionId = version.id`; `aspectMismatch = !aspectRatioMatches(frameWidth, frameHeight,
 *   version.frame_width, version.frame_height)`; `isDirty = false`; limpia selección, dibujo,
 *   `issues` y `warnings`. Con otra relación de aspecto NO se reproyecta ni se descarta nada: las
 *   figuras se estiran al frame nuevo (por eso la advertencia de deformación de FR-030) y, como
 *   el normalizado está en [0, 1], quedan dentro del frame.
 * - `{ type: "addShop", name }` — agrega al final un local nuevo (`shop_id: null`, sin zonas ni
 *   línea) y lo selecciona. Se ignora si ya hay `MAX_SHOPS_PER_VERSION` locales.
 * - `{ type: "renameShop", shopIndex, name }` — conserva `shop_id` y `key`.
 * - `{ type: "removeShop", shopIndex }` — quita solo ese local; descarta sus `issues` y corre el
 *   `shop_index` de los posteriores; limpia la selección o el dibujo que apuntaban a él y corre
 *   los índices de los posteriores.
 * - `{ type: "select", selection: EditorSelection | null }` — no marca `isDirty`.
 * - `{ type: "startDrawing", shopIndex, element }` — empieza a dibujar; se ignora si ese local ya
 *   tiene ese elemento (a lo sumo una zona por rol y una línea por local). No marca `isDirty`.
 * - `{ type: "addPoint", point }` — clic sobre el fondo en modo creación (punto limitado al
 *   frame). Sin dibujo en curso se ignora. En una zona agrega un vértice. En una línea, el primer
 *   clic fija `start` (queda en `drawing.points`) y el segundo la completa con
 *   `entry_direction: "a_to_b"` por defecto, termina el dibujo, selecciona la línea y marca
 *   `isDirty`.
 * - `{ type: "finishDrawing" }` — cierra el polígono en curso si tiene ≥ 3 vértices (lo guarda en
 *   el local, termina el dibujo, lo selecciona, marca `isDirty`); con menos, se ignora. El cierre
 *   es explícito (botón o Enter); no hay "clic sobre el primer vértice".
 * - `{ type: "cancelDrawing" }` — descarta el dibujo en curso sin tocar los locales.
 * - `{ type: "moveVertex", shopIndex, element, vertexIndex, point }` — posición absoluta (arrastre
 *   con el mouse), limitada al frame.
 * - `{ type: "nudgeVertex", shopIndex, element, vertexIndex, direction, large }` — teclado:
 *   `direction` ∈ `"up" | "down" | "left" | "right"` (y crece hacia abajo), 1 px o 10 px con
 *   `large` (Shift), limitado al frame.
 * - `{ type: "deleteVertex", shopIndex, element, vertexIndex }` — solo zonas; se ignora si la
 *   zona tiene 3 vértices o menos, y en líneas.
 * - `{ type: "deleteElement", shopIndex, element }` — quita la zona o la línea; limpia la
 *   selección si apuntaba a ese elemento.
 * - `{ type: "setZoneRole", shopIndex, from: ZoneRole, to: ZoneRole }` — cambia el rol de una zona;
 *   se ignora si el local ya tiene una zona con el rol `to`.
 * - `{ type: "setEntryDirection", shopIndex, direction: EntryDirection }` — se ignora sin línea.
 * - `{ type: "moveElementToShop", from: number, element: EditorElement, to: number }` — reasigna
 *   una zona o la línea a otro local (FR-031). Se ignora si `from === to`, si algún índice no
 *   existe, si el origen no tiene ese elemento o si el destino ya lo tiene (a lo sumo una zona
 *   por rol y una línea por local). El origen pierde el elemento, los demás locales y todos los
 *   `shop_id` quedan igual, y la selección pasa a `{ shopIndex: to, element, vertexIndex: null }`.
 * - `{ type: "saveSucceeded", version: SceneVersion, warnings: SceneIssue[] }` — `isDirty = false`,
 *   `baseVersionId = version.id`, asigna a cada local el `shop_id` de `version.shops` en la misma
 *   posición (los nuevos dejan de ser nuevos), `aspectMismatch = false` (la versión nueva ya está
 *   sobre este frame), `issues = []`, `warnings = warnings`. NO recarga las coordenadas: el
 *   dibujo sigue en los píxeles en que se dibujó.
 * - `{ type: "saveFailed", errors: SceneIssue[] }` — `issues = errors`; no toca `shops` ni
 *   `isDirty` (FR-034: no se descarta el dibujo).
 *
 * Toda acción que cambia `shops` marca `isDirty = true`; `aspectMismatch` solo cambia con
 * `loadVersion` y `saveSucceeded`.
 *
 * Limpieza de errores al editar: editar un elemento borra de `issues` los de ese `shop_index` +
 * `element`, porque ya no describen el dibujo actual. Cuentan como edición `moveVertex`,
 * `nudgeVertex`, `deleteVertex` y `deleteElement` (los del elemento), `setZoneRole` (los del rol
 * `from`), `setEntryDirection` (los de `entry_line`) y `moveElementToShop` (los del elemento en el
 * local de origen). `renameShop` borra los de nivel `shop` de ese local. Los errores de otros
 * elementos, de otros locales y los de nivel `version` se mantienen hasta el próximo guardado.
 * `removeShop` descarta los del local quitado y corre los índices (ver arriba).
 *
 * Selectores
 * - `issuesFor(state, shopIndex: number | null, element?: SceneIssueElement): SceneIssue[]` —
 *   `shopIndex = null` devuelve los errores de la versión; sin `element`, todos los de ese local.
 * - `hasIssue(state, shopIndex, element): boolean` — para resaltar un elemento en el canvas.
 * - `availableZoneRoles(state, shopIndex): ZoneRole[]` — roles sin zona en ese local, en el orden
 *   `front`, `interior`, `showcase` (para el `<select>` de "Crear zona").
 *
 * `toSceneVersionCreate` envía solo lo confirmado (nunca el dibujo en curso): `shop_id` (`null` si
 * es nuevo), `name`, las zonas presentes y `entry_line` (o `null`, que el backend rechaza con
 * `missing_entry_line`), y `base_version_id = state.baseVersionId`.
 */
import { describe, expect, it } from "vitest";

import { frameToNormalized } from "../src/editor/coordinates";
import {
  availableZoneRoles,
  createEditorState,
  editorReducer,
  hasIssue,
  issuesFor,
  toSceneVersionCreate,
  type EditorAction,
  type EditorShop,
  type EditorState,
} from "../src/editor/editorState";
import { MAX_SHOPS_PER_VERSION } from "../src/types/scene";
import type { Point, SceneIssue, SceneVersion } from "../src/types/scene";

// Frame de la sesión: 1280×720 (16:9). Los normalizados del fixture son fracciones binarias
// exactas (0,125, 0,25…) para que normalizado × frame sea exacto en punto flotante.
const FRAME_W = 1280;
const FRAME_H = 720;
const SESSION_ID = "session-1";

function emptyState(): EditorState {
  return createEditorState({ frameWidth: FRAME_W, frameHeight: FRAME_H });
}

function apply(state: EditorState, ...actions: EditorAction[]): EditorState {
  return actions.reduce<EditorState>((current, action) => editorReducer(current, action), state);
}

function version(overrides: Partial<SceneVersion> = {}): SceneVersion {
  return {
    id: "v-1",
    camera_id: "cam-1",
    version_number: 1,
    reference_session_id: "session-0",
    frame_width: 1920,
    frame_height: 1080,
    created_by_machine_id: "pc-lab-01",
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
          interior: [
            [0.125, 0.125],
            [0.375, 0.125],
            [0.25, 0.375],
          ],
        },
        entry_line: { start: [0.125, 0.875], end: [0.375, 0.875], entry_direction: "a_to_b" },
      },
      {
        shop_id: "shop-b",
        name: "Local B",
        zones: {
          front: [
            [0.625, 0.5],
            [0.875, 0.5],
            [0.75, 0.75],
          ],
        },
        entry_line: { start: [0.625, 0.875], end: [0.875, 0.875], entry_direction: "b_to_a" },
      },
    ],
    ...overrides,
  };
}

/** Estado con la versión de ejemplo cargada (misma relación de aspecto que la sesión). */
function loadedState(): EditorState {
  return apply(emptyState(), { type: "loadVersion", version: version() });
}

/** Estado con un solo local nuevo, sin elementos. */
function oneNewShop(): EditorState {
  return apply(emptyState(), { type: "addShop", name: "Local nuevo" });
}

function issue(overrides: Partial<SceneIssue>): SceneIssue {
  return {
    rule: "self_intersection",
    element: "zone:front",
    shop_index: 0,
    shop_name: "Local A",
    message: "La zona frontal se cruza a sí misma.",
    ...overrides,
  };
}

function expectPoints(actual: Point[] | undefined, expected: Point[]) {
  expect(actual).toBeDefined();
  expect(actual).toHaveLength(expected.length);
  actual!.forEach((point, index) => {
    expect(point[0]).toBeCloseTo(expected[index][0], 9);
    expect(point[1]).toBeCloseTo(expected[index][1], 9);
  });
}

// --- 1. Cargar una versión existente ------------------------------------------------

describe("createEditorState", () => {
  it("empieza vacío, limpio y sin versión base", () => {
    const state = emptyState();

    expect(state.frameWidth).toBe(FRAME_W);
    expect(state.frameHeight).toBe(FRAME_H);
    expect(state.baseVersionId).toBeNull();
    expect(state.shops).toEqual([]);
    expect(state.selection).toBeNull();
    expect(state.drawing).toBeNull();
    expect(state.isDirty).toBe(false);
    expect(state.aspectMismatch).toBe(false);
    expect(state.issues).toEqual([]);
    expect(state.warnings).toEqual([]);
  });
});

describe("loadVersion", () => {
  it("convierte las coordenadas normalizadas a píxeles del frame de la sesión", () => {
    const state = loadedState();

    expectPoints(state.shops[0].zones.front, [
      [160, 360],
      [480, 360],
      [480, 540],
      [160, 540],
    ]);
    expectPoints(state.shops[0].zones.interior, [
      [160, 90],
      [480, 90],
      [320, 270],
    ]);
    expect(state.shops[0].zones.showcase).toBeUndefined();
    expectPoints([state.shops[0].entry_line!.start, state.shops[0].entry_line!.end], [
      [160, 630],
      [480, 630],
    ]);
    expect(state.shops[1].entry_line!.entry_direction).toBe("b_to_a");
  });

  it("conserva shop_id, nombre y orden de los locales, con keys únicas", () => {
    const state = loadedState();

    expect(state.shops.map((shop: EditorShop) => shop.shop_id)).toEqual(["shop-a", "shop-b"]);
    expect(state.shops.map((shop: EditorShop) => shop.name)).toEqual(["Local A", "Local B"]);
    expect(new Set(state.shops.map((shop: EditorShop) => shop.key)).size).toBe(2);
  });

  it("toma la versión como base y queda limpio, sin advertencia de aspecto (1920×1080 vs 1280×720)", () => {
    const state = loadedState();

    expect(state.baseVersionId).toBe("v-1");
    expect(state.isDirty).toBe(false);
    expect(state.aspectMismatch).toBe(false);
    expect(state.selection).toBeNull();
    expect(state.drawing).toBeNull();
  });

  it("reemplaza todo lo anterior, incluidos errores y cambios sin guardar", () => {
    const dirty = apply(
      emptyState(),
      { type: "addShop", name: "Borrador" },
      { type: "saveFailed", errors: [issue({})] },
    );

    const state = apply(dirty, { type: "loadVersion", version: version() });

    expect(state.shops.map((shop: EditorShop) => shop.name)).toEqual(["Local A", "Local B"]);
    expect(state.issues).toEqual([]);
    expect(state.isDirty).toBe(false);
  });
});

// --- 2. Otra relación de aspecto (FR-030, US3-7) -------------------------------------

describe("loadVersion con otra relación de aspecto", () => {
  const fourByThree = version({ id: "v-43", frame_width: 640, frame_height: 480 });

  it("marca aspectMismatch y conserva todos los locales con su shop_id", () => {
    const state = apply(emptyState(), { type: "loadVersion", version: fourByThree });

    expect(state.aspectMismatch).toBe(true);
    expect(state.shops.map((shop: EditorShop) => shop.shop_id)).toEqual(["shop-a", "shop-b"]);
    expect(state.shops.map((shop: EditorShop) => shop.name)).toEqual(["Local A", "Local B"]);
    expect(state.baseVersionId).toBe("v-43");
    expect(state.isDirty).toBe(false);
  });

  it("estira las figuras al frame de la sesión: normalizado × 1280×720, no × 640×480", () => {
    const state = apply(emptyState(), { type: "loadVersion", version: fourByThree });

    // Mismo normalizado que la versión 16:9: por eso se ven deformadas y hay que revisarlas.
    expectPoints(state.shops[0].zones.front, [
      [160, 360],
      [480, 360],
      [480, 540],
      [160, 540],
    ]);
  });

  it("la advertencia persiste al editar y solo se va al guardar sobre este frame", () => {
    const mismatched = apply(emptyState(), { type: "loadVersion", version: fourByThree });

    const edited = apply(mismatched, { type: "renameShop", shopIndex: 0, name: "Local A2" });
    expect(edited.aspectMismatch).toBe(true);

    const saved = apply(edited, {
      type: "saveSucceeded",
      version: version({ id: "v-2", version_number: 2, frame_width: FRAME_W, frame_height: FRAME_H }),
      warnings: [],
    });
    expect(saved.aspectMismatch).toBe(false);
  });

  it("volver a cargar una versión con la misma relación de aspecto limpia la advertencia", () => {
    const state = apply(
      emptyState(),
      { type: "loadVersion", version: fourByThree },
      { type: "loadVersion", version: version() },
    );

    expect(state.aspectMismatch).toBe(false);
  });
});

// --- 3. Locales ----------------------------------------------------------------------

describe("locales", () => {
  it("agregar crea un local nuevo sin shop_id ni elementos y lo selecciona", () => {
    const state = apply(loadedState(), { type: "addShop", name: "Local C" });

    expect(state.shops).toHaveLength(3);
    const created = state.shops[2];
    expect(created.shop_id).toBeNull();
    expect(created.name).toBe("Local C");
    expect(created.zones).toEqual({});
    expect(created.entry_line).toBeNull();
    expect(new Set(state.shops.map((shop: EditorShop) => shop.key)).size).toBe(3);
    expect(state.selection).toEqual({ shopIndex: 2, element: null, vertexIndex: null });
  });

  it(`no agrega más de ${MAX_SHOPS_PER_VERSION} locales`, () => {
    let state = emptyState();
    for (let i = 0; i < MAX_SHOPS_PER_VERSION; i += 1) {
      state = apply(state, { type: "addShop", name: `Local ${i}` });
    }

    const next = apply(state, { type: "addShop", name: "Uno de más" });

    expect(next).toBe(state);
    expect(next.shops).toHaveLength(MAX_SHOPS_PER_VERSION);
  });

  it("renombrar conserva shop_id, key y geometría", () => {
    const before = loadedState();

    const state = apply(before, { type: "renameShop", shopIndex: 0, name: "Local A renombrado" });

    expect(state.shops[0].name).toBe("Local A renombrado");
    expect(state.shops[0].shop_id).toBe("shop-a");
    expect(state.shops[0].key).toBe(before.shops[0].key);
    expect(state.shops[0].zones).toEqual(before.shops[0].zones);
    expect(state.shops[0].entry_line).toEqual(before.shops[0].entry_line);
  });

  it("quitar un local no afecta a los otros", () => {
    const before = loadedState();

    const state = apply(before, { type: "removeShop", shopIndex: 0 });

    expect(state.shops).toHaveLength(1);
    expect(state.shops[0]).toEqual(before.shops[1]);
  });

  it("quitar el local seleccionado limpia la selección; quitar uno anterior corre el índice", () => {
    const selectedFirst = apply(loadedState(), {
      type: "select",
      selection: { shopIndex: 0, element: "zone:front", vertexIndex: null },
    });
    expect(apply(selectedFirst, { type: "removeShop", shopIndex: 0 }).selection).toBeNull();

    const selectedSecond = apply(loadedState(), {
      type: "select",
      selection: { shopIndex: 1, element: "entry_line", vertexIndex: 1 },
    });
    expect(apply(selectedSecond, { type: "removeShop", shopIndex: 0 }).selection).toEqual({
      shopIndex: 0,
      element: "entry_line",
      vertexIndex: 1,
    });
  });

  it("ignora índices inexistentes", () => {
    const before = loadedState();

    expect(apply(before, { type: "renameShop", shopIndex: 5, name: "X" })).toBe(before);
    expect(apply(before, { type: "removeShop", shopIndex: -1 })).toBe(before);
  });
});

// --- 4. Polígonos y línea --------------------------------------------------------------

describe("crear un polígono por clics", () => {
  const clicks: Point[] = [
    [100, 100],
    [300, 100],
    [300, 250],
    [100, 250],
  ];

  it("acumula los vértices en el dibujo en curso sin tocar el local", () => {
    const state = apply(
      oneNewShop(),
      { type: "startDrawing", shopIndex: 0, element: "zone:front" },
      { type: "addPoint", point: clicks[0] },
      { type: "addPoint", point: clicks[1] },
    );

    expect(state.drawing).toEqual({ shopIndex: 0, element: "zone:front", points: [clicks[0], clicks[1]] });
    expect(state.shops[0].zones.front).toBeUndefined();
  });

  it("al cerrarlo lo guarda en el local con su rol, termina el dibujo y lo selecciona", () => {
    const state = apply(
      oneNewShop(),
      { type: "startDrawing", shopIndex: 0, element: "zone:front" },
      ...clicks.map((point): EditorAction => ({ type: "addPoint", point })),
      { type: "finishDrawing" },
    );

    expect(state.shops[0].zones.front).toEqual(clicks);
    expect(state.drawing).toBeNull();
    expect(state.selection).toEqual({ shopIndex: 0, element: "zone:front", vertexIndex: null });
  });

  it("no cierra un polígono de menos de 3 vértices", () => {
    const drawing = apply(
      oneNewShop(),
      { type: "startDrawing", shopIndex: 0, element: "zone:interior" },
      { type: "addPoint", point: clicks[0] },
      { type: "addPoint", point: clicks[1] },
    );

    const state = apply(drawing, { type: "finishDrawing" });

    expect(state).toBe(drawing);
    expect(state.shops[0].zones.interior).toBeUndefined();
  });

  it("limita al frame los clics fuera de la imagen", () => {
    const state = apply(
      oneNewShop(),
      { type: "startDrawing", shopIndex: 0, element: "zone:showcase" },
      { type: "addPoint", point: [-20, 50] },
      { type: "addPoint", point: [FRAME_W + 5, 50] },
      { type: "addPoint", point: [640, FRAME_H + 30] },
      { type: "finishDrawing" },
    );

    expect(state.shops[0].zones.showcase).toEqual([
      [0, 50],
      [FRAME_W, 50],
      [640, FRAME_H],
    ]);
  });

  it("cancelar descarta el dibujo en curso sin tocar el local", () => {
    const base = oneNewShop();

    const state = apply(
      base,
      { type: "startDrawing", shopIndex: 0, element: "zone:front" },
      { type: "addPoint", point: clicks[0] },
      { type: "cancelDrawing" },
    );

    expect(state.drawing).toBeNull();
    expect(state.shops).toEqual(base.shops);
  });

  it("sin dibujo en curso, un clic sobre el fondo no hace nada", () => {
    const base = oneNewShop();

    expect(apply(base, { type: "addPoint", point: [10, 10] })).toBe(base);
    expect(apply(base, { type: "finishDrawing" })).toBe(base);
  });
});

describe("crear una línea con dos clics", () => {
  it("el primer clic fija el inicio en el dibujo en curso", () => {
    const state = apply(
      oneNewShop(),
      { type: "startDrawing", shopIndex: 0, element: "entry_line" },
      { type: "addPoint", point: [200, 600] },
    );

    expect(state.drawing).toEqual({ shopIndex: 0, element: "entry_line", points: [[200, 600]] });
    expect(state.shops[0].entry_line).toBeNull();
  });

  it("el segundo clic la completa con sentido a_to_b, termina el dibujo y la selecciona", () => {
    const state = apply(
      oneNewShop(),
      { type: "startDrawing", shopIndex: 0, element: "entry_line" },
      { type: "addPoint", point: [200, 600] },
      { type: "addPoint", point: [700, 600] },
    );

    expect(state.shops[0].entry_line).toEqual({
      start: [200, 600],
      end: [700, 600],
      entry_direction: "a_to_b",
    });
    expect(state.drawing).toBeNull();
    expect(state.selection).toEqual({ shopIndex: 0, element: "entry_line", vertexIndex: null });
    expect(state.isDirty).toBe(true);
  });

  it("no empieza una segunda línea en un local que ya tiene una", () => {
    const base = loadedState();

    expect(apply(base, { type: "startDrawing", shopIndex: 0, element: "entry_line" })).toBe(base);
  });
});

// --- 5. Mover vértices y extremos --------------------------------------------------------

describe("mover vértices con el mouse", () => {
  it("mueve un vértice de una zona a la posición indicada", () => {
    const state = apply(loadedState(), {
      type: "moveVertex",
      shopIndex: 0,
      element: "zone:front",
      vertexIndex: 2,
      point: [500, 555],
    });

    expect(state.shops[0].zones.front![2]).toEqual([500, 555]);
    expect(state.shops[0].zones.front![0]).toEqual(loadedState().shops[0].zones.front![0]);
  });

  it("mueve el extremo final de una línea (vertexIndex 1) sin tocar el inicio ni el sentido", () => {
    const before = loadedState();

    const state = apply(before, {
      type: "moveVertex",
      shopIndex: 1,
      element: "entry_line",
      vertexIndex: 1,
      point: [1200, 650],
    });

    expect(state.shops[1].entry_line).toEqual({
      start: before.shops[1].entry_line!.start,
      end: [1200, 650],
      entry_direction: "b_to_a",
    });
  });

  it("limita al frame un arrastre que sale de la imagen", () => {
    const state = apply(loadedState(), {
      type: "moveVertex",
      shopIndex: 1,
      element: "entry_line",
      vertexIndex: 0,
      point: [-40, FRAME_H + 100],
    });

    expect(state.shops[1].entry_line!.start).toEqual([0, FRAME_H]);
  });

  it("ignora un vértice o un elemento inexistente", () => {
    const base = loadedState();

    expect(
      apply(base, { type: "moveVertex", shopIndex: 0, element: "zone:front", vertexIndex: 9, point: [1, 1] }),
    ).toBe(base);
    expect(
      apply(base, { type: "moveVertex", shopIndex: 1, element: "zone:showcase", vertexIndex: 0, point: [1, 1] }),
    ).toBe(base);
  });
});

describe("mover vértices con el teclado", () => {
  // Local A: front[0] = (160, 360); línea de B: start = (800, 630).
  it.each([
    ["right", false, [161, 360]],
    ["left", false, [159, 360]],
    ["down", false, [160, 361]],
    ["up", false, [160, 359]],
    ["right", true, [170, 360]],
    ["left", true, [150, 360]],
    ["down", true, [160, 370]],
    ["up", true, [160, 350]],
  ] as const)("%s con large=%s mueve a %j", (direction, large, expected) => {
    const state = apply(loadedState(), {
      type: "nudgeVertex",
      shopIndex: 0,
      element: "zone:front",
      vertexIndex: 0,
      direction,
      large,
    });

    expect(state.shops[0].zones.front![0]).toEqual(expected);
  });

  it("mueve también un extremo de la línea", () => {
    const state = apply(loadedState(), {
      type: "nudgeVertex",
      shopIndex: 1,
      element: "entry_line",
      vertexIndex: 0,
      direction: "up",
      large: true,
    });

    expect(state.shops[1].entry_line!.start).toEqual([800, 620]);
  });

  it("no sale del frame, ni con pasos de 1 px ni de 10 px", () => {
    const atCorner = apply(
      oneNewShop(),
      { type: "startDrawing", shopIndex: 0, element: "zone:front" },
      { type: "addPoint", point: [0, 0] },
      { type: "addPoint", point: [FRAME_W - 4, 100] },
      { type: "addPoint", point: [100, FRAME_H - 1] },
      { type: "finishDrawing" },
    );
    const nudge = (vertexIndex: number, direction: "up" | "down" | "left" | "right", large: boolean) =>
      apply(atCorner, { type: "nudgeVertex", shopIndex: 0, element: "zone:front", vertexIndex, direction, large })
        .shops[0].zones.front![vertexIndex];

    expect(nudge(0, "left", false)).toEqual([0, 0]);
    expect(nudge(0, "up", true)).toEqual([0, 0]);
    expect(nudge(1, "right", true)).toEqual([FRAME_W, 100]);
    expect(nudge(2, "down", false)).toEqual([100, FRAME_H]);
    expect(nudge(2, "down", true)).toEqual([100, FRAME_H]);
  });
});

// --- 6. Eliminar vértices y elementos ------------------------------------------------------

describe("eliminar", () => {
  it("elimina un vértice de una zona con más de 3", () => {
    const before = loadedState();

    const state = apply(before, { type: "deleteVertex", shopIndex: 0, element: "zone:front", vertexIndex: 1 });

    expect(state.shops[0].zones.front).toEqual([
      before.shops[0].zones.front![0],
      before.shops[0].zones.front![2],
      before.shops[0].zones.front![3],
    ]);
  });

  it("no baja una zona de 3 vértices", () => {
    const base = loadedState();

    // interior de A tiene 3 vértices.
    expect(apply(base, { type: "deleteVertex", shopIndex: 0, element: "zone:interior", vertexIndex: 0 })).toBe(base);
  });

  it("no elimina extremos de una línea", () => {
    const base = loadedState();

    expect(apply(base, { type: "deleteVertex", shopIndex: 0, element: "entry_line", vertexIndex: 0 })).toBe(base);
  });

  it("eliminar un vértice seleccionado deja seleccionado el elemento, sin vértice", () => {
    const state = apply(
      loadedState(),
      { type: "select", selection: { shopIndex: 0, element: "zone:front", vertexIndex: 3 } },
      { type: "deleteVertex", shopIndex: 0, element: "zone:front", vertexIndex: 3 },
    );

    expect(state.selection).toEqual({ shopIndex: 0, element: "zone:front", vertexIndex: null });
  });

  it("elimina una zona sin tocar las demás ni la línea", () => {
    const before = loadedState();

    const state = apply(before, { type: "deleteElement", shopIndex: 0, element: "zone:interior" });

    expect(state.shops[0].zones.interior).toBeUndefined();
    expect(state.shops[0].zones.front).toEqual(before.shops[0].zones.front);
    expect(state.shops[0].entry_line).toEqual(before.shops[0].entry_line);
    expect(state.shops[1]).toEqual(before.shops[1]);
  });

  it("elimina la línea de entrada y limpia la selección que apuntaba a ella", () => {
    const state = apply(
      loadedState(),
      { type: "select", selection: { shopIndex: 1, element: "entry_line", vertexIndex: 0 } },
      { type: "deleteElement", shopIndex: 1, element: "entry_line" },
    );

    expect(state.shops[1].entry_line).toBeNull();
    expect(state.selection).toBeNull();
  });
});

// --- 7. Roles ----------------------------------------------------------------------------

describe("roles de zona", () => {
  it("cambia el rol de una zona a uno libre", () => {
    const before = loadedState();

    const state = apply(before, { type: "setZoneRole", shopIndex: 0, from: "interior", to: "showcase" });

    expect(state.shops[0].zones.interior).toBeUndefined();
    expect(state.shops[0].zones.showcase).toEqual(before.shops[0].zones.interior);
  });

  it("no asigna un rol que el local ya tiene (a lo sumo una zona por rol)", () => {
    const base = loadedState();

    expect(apply(base, { type: "setZoneRole", shopIndex: 0, from: "interior", to: "front" })).toBe(base);
  });

  it("no empieza a dibujar una zona con un rol ya ocupado", () => {
    const base = loadedState();

    expect(apply(base, { type: "startDrawing", shopIndex: 0, element: "zone:front" })).toBe(base);
  });

  it("el mismo rol sí puede repetirse en locales distintos", () => {
    const state = apply(
      loadedState(),
      { type: "startDrawing", shopIndex: 1, element: "zone:interior" },
      { type: "addPoint", point: [800, 100] },
      { type: "addPoint", point: [1100, 100] },
      { type: "addPoint", point: [950, 250] },
      { type: "finishDrawing" },
    );

    expect(state.shops[0].zones.interior).toBeDefined();
    expect(state.shops[1].zones.interior).toHaveLength(3);
  });

  it("availableZoneRoles lista los roles libres de cada local", () => {
    const state = loadedState();

    expect(availableZoneRoles(state, 0)).toEqual(["showcase"]);
    expect(availableZoneRoles(state, 1)).toEqual(["interior", "showcase"]);
    expect(availableZoneRoles(oneNewShop(), 0)).toEqual(["front", "interior", "showcase"]);
  });
});

// --- 8. Sentido de entrada ------------------------------------------------------------------

describe("sentido de entrada", () => {
  it("cambia entry_direction sin mover la línea", () => {
    const before = loadedState();

    const state = apply(before, { type: "setEntryDirection", shopIndex: 0, direction: "b_to_a" });

    expect(state.shops[0].entry_line).toEqual({ ...before.shops[0].entry_line!, entry_direction: "b_to_a" });
    expect(state.isDirty).toBe(true);
  });

  it("se ignora en un local sin línea", () => {
    const base = oneNewShop();

    expect(apply(base, { type: "setEntryDirection", shopIndex: 0, direction: "b_to_a" })).toBe(base);
  });
});

// --- Reasignar un elemento a otro local (FR-031) ------------------------------------------------

describe("moveElementToShop", () => {
  it("mueve una zona a un local con ese rol libre y la selecciona allí", () => {
    const before = loadedState();

    const state = apply(before, { type: "moveElementToShop", from: 0, element: "zone:interior", to: 1 });

    expect(state.shops[1].zones.interior).toEqual(before.shops[0].zones.interior);
    expect(state.shops[1].zones.front).toEqual(before.shops[1].zones.front);
    expect(state.shops[0].zones.interior).toBeUndefined();
    expect(state.shops[0].zones.front).toEqual(before.shops[0].zones.front);
    expect(state.shops[0].entry_line).toEqual(before.shops[0].entry_line);
    expect(state.selection).toEqual({ shopIndex: 1, element: "zone:interior", vertexIndex: null });
    expect(state.isDirty).toBe(true);
    expect(state.shops.map((shop: EditorShop) => shop.shop_id)).toEqual(["shop-a", "shop-b"]);
  });

  it("no toca los otros locales", () => {
    const before = apply(loadedState(), { type: "addShop", name: "Local C" });

    const state = apply(before, { type: "moveElementToShop", from: 0, element: "zone:interior", to: 2 });

    expect(state.shops[2].zones.interior).toEqual(before.shops[0].zones.interior);
    expect(state.shops[1]).toEqual(before.shops[1]);
    expect(state.shops.map((shop: EditorShop) => shop.key)).toEqual(before.shops.map((shop: EditorShop) => shop.key));
  });

  it("rechaza una zona cuyo rol ya está ocupado en el destino", () => {
    const base = loadedState();

    expect(apply(base, { type: "moveElementToShop", from: 0, element: "zone:front", to: 1 })).toBe(base);
  });

  it("mueve la línea a un local sin línea", () => {
    const before = apply(loadedState(), { type: "deleteElement", shopIndex: 1, element: "entry_line" });

    const state = apply(before, { type: "moveElementToShop", from: 0, element: "entry_line", to: 1 });

    expect(state.shops[1].entry_line).toEqual(before.shops[0].entry_line);
    expect(state.shops[0].entry_line).toBeNull();
    expect(state.selection).toEqual({ shopIndex: 1, element: "entry_line", vertexIndex: null });
  });

  it("rechaza la línea si el destino ya tiene una", () => {
    const base = loadedState();

    expect(apply(base, { type: "moveElementToShop", from: 0, element: "entry_line", to: 1 })).toBe(base);
  });

  it("no hace nada con from === to, índices inexistentes o un elemento que el origen no tiene", () => {
    const base = loadedState();

    expect(apply(base, { type: "moveElementToShop", from: 0, element: "zone:interior", to: 0 })).toBe(base);
    expect(apply(base, { type: "moveElementToShop", from: 0, element: "zone:interior", to: 7 })).toBe(base);
    expect(apply(base, { type: "moveElementToShop", from: -1, element: "zone:front", to: 1 })).toBe(base);
    expect(apply(base, { type: "moveElementToShop", from: 0, element: "zone:showcase", to: 1 })).toBe(base);
  });
});

// --- 9. isDirty -------------------------------------------------------------------------------

describe("isDirty", () => {
  const changes: Array<[string, EditorAction]> = [
    ["addShop", { type: "addShop", name: "Local C" }],
    ["renameShop", { type: "renameShop", shopIndex: 0, name: "Otro" }],
    ["removeShop", { type: "removeShop", shopIndex: 1 }],
    ["moveVertex", { type: "moveVertex", shopIndex: 0, element: "zone:front", vertexIndex: 0, point: [10, 10] }],
    [
      "nudgeVertex",
      { type: "nudgeVertex", shopIndex: 0, element: "zone:front", vertexIndex: 0, direction: "up", large: false },
    ],
    ["deleteVertex", { type: "deleteVertex", shopIndex: 0, element: "zone:front", vertexIndex: 0 }],
    ["deleteElement", { type: "deleteElement", shopIndex: 0, element: "zone:interior" }],
    ["setZoneRole", { type: "setZoneRole", shopIndex: 0, from: "interior", to: "showcase" }],
    ["setEntryDirection", { type: "setEntryDirection", shopIndex: 0, direction: "b_to_a" }],
    ["moveElementToShop", { type: "moveElementToShop", from: 0, element: "zone:interior", to: 1 }],
  ];

  it.each(changes)("%s lo pasa a true", (_label, action) => {
    expect(apply(loadedState(), action).isDirty).toBe(true);
  });

  it("cerrar un polígono lo pasa a true", () => {
    const state = apply(
      loadedState(),
      { type: "startDrawing", shopIndex: 0, element: "zone:showcase" },
      { type: "addPoint", point: [600, 100] },
      { type: "addPoint", point: [700, 100] },
      { type: "addPoint", point: [650, 200] },
    );
    expect(state.isDirty).toBe(false);

    expect(apply(state, { type: "finishDrawing" }).isDirty).toBe(true);
  });

  it("seleccionar, empezar o cancelar un dibujo no lo cambian", () => {
    const state = apply(
      loadedState(),
      { type: "select", selection: { shopIndex: 1, element: "zone:front", vertexIndex: 2 } },
      { type: "startDrawing", shopIndex: 1, element: "zone:showcase" },
      { type: "addPoint", point: [900, 100] },
      { type: "cancelDrawing" },
    );

    expect(state.isDirty).toBe(false);
  });

  it("vuelve a false tras guardar, y asigna los shop_id de la versión nueva a los locales nuevos", () => {
    const edited = apply(loadedState(), { type: "addShop", name: "Local C" });
    expect(edited.isDirty).toBe(true);

    const saved = version({ id: "v-2", version_number: 2, frame_width: FRAME_W, frame_height: FRAME_H });
    saved.shops = [
      ...saved.shops,
      { shop_id: "shop-c", name: "Local C", zones: {}, entry_line: saved.shops[0].entry_line },
    ];
    const state = apply(edited, { type: "saveSucceeded", version: saved, warnings: [] });

    expect(state.isDirty).toBe(false);
    expect(state.baseVersionId).toBe("v-2");
    expect(state.shops.map((shop: EditorShop) => shop.shop_id)).toEqual(["shop-a", "shop-b", "shop-c"]);
    expect(state.shops.map((shop: EditorShop) => shop.key)).toEqual(edited.shops.map((shop: EditorShop) => shop.key));
  });

  it("guardar no recarga las coordenadas: el dibujo queda en los píxeles dibujados", () => {
    const edited = apply(loadedState(), {
      type: "moveVertex",
      shopIndex: 0,
      element: "zone:front",
      vertexIndex: 0,
      point: [161.37, 359.91],
    });

    const state = apply(edited, {
      type: "saveSucceeded",
      version: version({ id: "v-2", frame_width: FRAME_W, frame_height: FRAME_H }),
      warnings: [],
    });

    expect(state.shops[0].zones).toEqual(edited.shops[0].zones);
  });

  it("guarda las advertencias del guardado exitoso y limpia los errores anteriores", () => {
    const warning = issue({ rule: "line_not_touching_zones", element: "entry_line", shop_index: 1 });
    const failed = apply(
      loadedState(),
      { type: "renameShop", shopIndex: 0, name: "X" },
      { type: "saveFailed", errors: [issue({})] },
    );

    const state = apply(failed, {
      type: "saveSucceeded",
      version: version({ id: "v-2", frame_width: FRAME_W, frame_height: FRAME_H }),
      warnings: [warning],
    });

    expect(state.issues).toEqual([]);
    expect(state.warnings).toEqual([warning]);
  });

  it("sigue en true si el guardado falla", () => {
    const edited = apply(loadedState(), { type: "renameShop", shopIndex: 0, name: "Otro" });

    expect(apply(edited, { type: "saveFailed", errors: [issue({})] }).isDirty).toBe(true);
  });
});

// --- 10. toSceneVersionCreate -----------------------------------------------------------------

describe("toSceneVersionCreate", () => {
  it("normaliza a 6 decimales solo al guardar y deja el estado en píxeles", () => {
    const state = apply(
      oneNewShop(),
      { type: "startDrawing", shopIndex: 0, element: "zone:front" },
      { type: "addPoint", point: [333, 111] },
      { type: "addPoint", point: [640, 111] },
      { type: "addPoint", point: [640, 360] },
      { type: "finishDrawing" },
      { type: "startDrawing", shopIndex: 0, element: "entry_line" },
      { type: "addPoint", point: [320, 540] },
      { type: "addPoint", point: [960, 540] },
    );
    const snapshot = JSON.parse(JSON.stringify(state)) as EditorState;

    const payload = toSceneVersionCreate(state, SESSION_ID, FRAME_W, FRAME_H);

    expect(payload.shops[0].zones.front).toEqual([
      frameToNormalized([333, 111], FRAME_W, FRAME_H),
      [0.5, 0.154167],
      [0.5, 0.5],
    ]);
    // 333/1280 = 0,26015625 → 0,260156; 111/720 = 0,1541666… → 0,154167.
    expect(payload.shops[0].zones.front![0]).toEqual([0.260156, 0.154167]);
    expect(payload.shops[0].entry_line).toEqual({ start: [0.25, 0.75], end: [0.75, 0.75], entry_direction: "a_to_b" });
    expect(state).toEqual(snapshot);
    expect(state.shops[0].zones.front![0]).toEqual([333, 111]);
  });

  it("arma el payload completo: sesión, base_version_id y locales en orden con su shop_id", () => {
    const state = apply(loadedState(), { type: "renameShop", shopIndex: 1, name: "Local B2" });

    const payload = toSceneVersionCreate(state, SESSION_ID, FRAME_W, FRAME_H);

    expect(payload.reference_session_id).toBe(SESSION_ID);
    expect(payload.base_version_id).toBe("v-1");
    expect(payload.shops.map((shop) => [shop.shop_id, shop.name])).toEqual([
      ["shop-a", "Local A"],
      ["shop-b", "Local B2"],
    ]);
    expect(Object.keys(payload.shops[0].zones).sort()).toEqual(["front", "interior"]);
    expect(payload.shops[1].entry_line!.entry_direction).toBe("b_to_a");
    // La key interna no viaja a la API.
    expect(payload.shops[0]).not.toHaveProperty("key");
  });

  it("devuelve las mismas coordenadas normalizadas que la versión cargada (sin editar)", () => {
    const payload = toSceneVersionCreate(loadedState(), SESSION_ID, FRAME_W, FRAME_H);
    const original = version();

    original.shops.forEach((shop, index) => {
      expect(payload.shops[index].zones).toEqual(shop.zones);
      expect(payload.shops[index].entry_line).toEqual(shop.entry_line);
    });
  });

  it("sin versión cargada envía base_version_id null, shop_id null y entry_line null si falta", () => {
    const payload = toSceneVersionCreate(oneNewShop(), SESSION_ID, FRAME_W, FRAME_H);

    expect(payload).toEqual({
      reference_session_id: SESSION_ID,
      base_version_id: null,
      shops: [{ shop_id: null, name: "Local nuevo", zones: {}, entry_line: null }],
    });
  });

  it("no incluye el dibujo en curso", () => {
    const state = apply(
      oneNewShop(),
      { type: "startDrawing", shopIndex: 0, element: "zone:front" },
      { type: "addPoint", point: [10, 10] },
      { type: "addPoint", point: [100, 10] },
      { type: "addPoint", point: [100, 100] },
    );

    expect(toSceneVersionCreate(state, SESSION_ID, FRAME_W, FRAME_H).shops[0].zones).toEqual({});
  });

  it("tras guardar, el siguiente payload usa la versión nueva como base", () => {
    const state = apply(loadedState(), { type: "renameShop", shopIndex: 0, name: "Otro" }, {
      type: "saveSucceeded",
      version: version({ id: "v-2", version_number: 2, frame_width: FRAME_W, frame_height: FRAME_H }),
      warnings: [],
    });

    expect(toSceneVersionCreate(state, SESSION_ID, FRAME_W, FRAME_H).base_version_id).toBe("v-2");
  });
});

// --- 11. Errores de la API ------------------------------------------------------------------------

describe("errores de la API (saveFailed)", () => {
  const errors: SceneIssue[] = [
    issue({ rule: "self_intersection", element: "zone:front", shop_index: 0 }),
    issue({ rule: "area_too_small", element: "zone:front", shop_index: 0, message: "Área chica." }),
    issue({ rule: "line_too_short", element: "entry_line", shop_index: 1, shop_name: "Local B" }),
    issue({ rule: "duplicate_shop_name", element: "shop", shop_index: 1, shop_name: "Local B" }),
    issue({ rule: "reference_frame_missing", element: "version", shop_index: null, shop_name: null }),
  ];

  it("no descarta el dibujo ni la selección", () => {
    const before = apply(loadedState(), {
      type: "select",
      selection: { shopIndex: 0, element: "zone:front", vertexIndex: 1 },
    });

    const state = apply(before, { type: "saveFailed", errors });

    expect(state.shops).toEqual(before.shops);
    expect(state.selection).toEqual(before.selection);
    expect(state.baseVersionId).toBe("v-1");
    expect(state.issues).toEqual(errors);
  });

  it("se consultan por shop_index + element", () => {
    const state = apply(loadedState(), { type: "saveFailed", errors });

    expect(issuesFor(state, 0, "zone:front").map((item: SceneIssue) => item.rule)).toEqual(["self_intersection", "area_too_small"]);
    expect(issuesFor(state, 0, "entry_line")).toEqual([]);
    expect(issuesFor(state, 1, "entry_line").map((item: SceneIssue) => item.rule)).toEqual(["line_too_short"]);
    expect(issuesFor(state, 1, "shop").map((item: SceneIssue) => item.rule)).toEqual(["duplicate_shop_name"]);
    expect(issuesFor(state, 1).map((item: SceneIssue) => item.rule)).toEqual(["line_too_short", "duplicate_shop_name"]);
    expect(issuesFor(state, null).map((item: SceneIssue) => item.rule)).toEqual(["reference_frame_missing"]);
  });

  it("hasIssue indica qué elementos resaltar", () => {
    const state = apply(loadedState(), { type: "saveFailed", errors });

    expect(hasIssue(state, 0, "zone:front")).toBe(true);
    expect(hasIssue(state, 0, "zone:interior")).toBe(false);
    expect(hasIssue(state, 1, "entry_line")).toBe(true);
    expect(hasIssue(state, 1, "zone:front")).toBe(false);
  });

  it("un nuevo intento fallido reemplaza los errores anteriores", () => {
    const state = apply(
      loadedState(),
      { type: "saveFailed", errors },
      { type: "saveFailed", errors: [errors[2]] },
    );

    expect(state.issues).toEqual([errors[2]]);
    expect(hasIssue(state, 0, "zone:front")).toBe(false);
  });

  it("quitar un local descarta sus errores y corre el shop_index de los posteriores", () => {
    const state = apply(loadedState(), { type: "saveFailed", errors }, { type: "removeShop", shopIndex: 0 });

    expect(issuesFor(state, 0, "entry_line").map((item: SceneIssue) => item.rule)).toEqual(["line_too_short"]);
    expect(issuesFor(state, 0, "shop").map((item: SceneIssue) => item.rule)).toEqual(["duplicate_shop_name"]);
    expect(issuesFor(state, 1)).toEqual([]);
    expect(issuesFor(state, null)).toHaveLength(1);
    expect(state.issues.some((item: SceneIssue) => item.rule === "self_intersection")).toBe(false);
  });
});

describe("errores de la API al editar", () => {
  const frontError = issue({ rule: "self_intersection", element: "zone:front", shop_index: 0 });
  const interiorError = issue({ rule: "area_too_small", element: "zone:interior", shop_index: 0 });
  const shopError = issue({ rule: "duplicate_shop_name", element: "shop", shop_index: 0 });
  const lineError = issue({ rule: "line_too_short", element: "entry_line", shop_index: 0 });
  const otherShopFrontError = issue({
    rule: "vertices_too_close",
    element: "zone:front",
    shop_index: 1,
    shop_name: "Local B",
  });
  const versionError = issue({
    rule: "reference_frame_missing",
    element: "version",
    shop_index: null,
    shop_name: null,
  });
  const errors = [frontError, interiorError, shopError, lineError, otherShopFrontError, versionError];

  function failed(): EditorState {
    return apply(loadedState(), { type: "saveFailed", errors });
  }

  it("moveVertex borra solo los errores del elemento editado", () => {
    const state = apply(failed(), {
      type: "moveVertex",
      shopIndex: 0,
      element: "zone:front",
      vertexIndex: 0,
      point: [170, 370],
    });

    expect(hasIssue(state, 0, "zone:front")).toBe(false);
    expect(state.issues).toEqual([interiorError, shopError, lineError, otherShopFrontError, versionError]);
  });

  it("renameShop borra los errores de nivel shop de ese local, no los de sus zonas", () => {
    const state = apply(failed(), { type: "renameShop", shopIndex: 0, name: "Local A único" });

    expect(issuesFor(state, 0, "shop")).toEqual([]);
    expect(issuesFor(state, 0, "zone:front")).toEqual([frontError]);
    expect(issuesFor(state, 0, "zone:interior")).toEqual([interiorError]);
  });

  const edits: Array<[string, EditorAction, SceneIssue[]]> = [
    ["moveVertex", { type: "moveVertex", shopIndex: 0, element: "zone:front", vertexIndex: 1, point: [490, 350] }, [frontError]],
    [
      "nudgeVertex",
      { type: "nudgeVertex", shopIndex: 0, element: "zone:front", vertexIndex: 0, direction: "right", large: true },
      [frontError],
    ],
    ["deleteVertex", { type: "deleteVertex", shopIndex: 0, element: "zone:front", vertexIndex: 3 }, [frontError]],
    ["deleteElement", { type: "deleteElement", shopIndex: 0, element: "zone:interior" }, [interiorError]],
    ["setZoneRole (rol anterior)", { type: "setZoneRole", shopIndex: 0, from: "interior", to: "showcase" }, [interiorError]],
    ["setEntryDirection", { type: "setEntryDirection", shopIndex: 0, direction: "b_to_a" }, [lineError]],
    [
      "moveElementToShop (local de origen)",
      { type: "moveElementToShop", from: 0, element: "zone:interior", to: 1 },
      [interiorError],
    ],
    ["renameShop", { type: "renameShop", shopIndex: 0, name: "Otro" }, [shopError]],
  ];

  it.each(edits)("%s borra solo sus errores; los de otros elementos, locales y version siguen", (_label, action, removed) => {
    const state = apply(failed(), action);

    expect(state.issues).toEqual(errors.filter((item) => !removed.includes(item)));
    expect(issuesFor(state, null)).toEqual([versionError]);
    expect(issuesFor(state, 1, "zone:front")).toEqual([otherShopFrontError]);
  });

  it("una acción rechazada no borra errores", () => {
    const base = failed();

    const state = apply(base, { type: "setZoneRole", shopIndex: 0, from: "interior", to: "front" });

    expect(state).toBe(base);
    expect(state.issues).toEqual(errors);
  });
});
