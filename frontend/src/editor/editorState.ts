import {
  aspectRatioMatches,
  clampToFrame,
  frameToNormalized,
  normalizedToFrame,
} from "./coordinates";
import {
  MAX_SHOPS_PER_VERSION,
  type EntryDirection,
  type EntryLine,
  type Point,
  type SceneIssue,
  type SceneIssueElement,
  type SceneVersion,
  type SceneVersionCreate,
  type ShopInput,
  type ZoneRole,
  type Zones,
} from "../types/scene";

/**
 * Estado del editor de escenas (T041): reducer puro para `useReducer`, sin DOM.
 *
 * Todas las coordenadas están en píxeles del frame de referencia de la sesión; solo
 * `toSceneVersionCreate` normaliza (FR-033). Una acción que no aplica devuelve el mismo objeto
 * `state`. El contrato completo está en la cabecera de `tests/editorState.test.ts`.
 */

/** Zona o línea de un local: los mismos valores que `SceneIssueElement` usa para ellas. */
export type EditorElement = `zone:${ZoneRole}` | "entry_line";

export interface EditorShop {
  /** Estable y único dentro del editor (para `key` de React); no se envía a la API. */
  key: string;
  /** `null` = local nuevo. */
  shop_id: string | null;
  name: string;
  zones: Zones;
  entry_line: EntryLine | null;
}

export interface EditorSelection {
  shopIndex: number;
  element: EditorElement | null;
  /** En una línea, 0 = `start` y 1 = `end`. */
  vertexIndex: number | null;
}

export interface EditorDrawing {
  shopIndex: number;
  element: EditorElement;
  points: Point[];
}

export interface EditorState {
  frameWidth: number;
  frameHeight: number;
  baseVersionId: string | null;
  shops: EditorShop[];
  selection: EditorSelection | null;
  drawing: EditorDrawing | null;
  isDirty: boolean;
  aspectMismatch: boolean;
  /** Errores del último 422. */
  issues: SceneIssue[];
  /** Advertencias del último guardado exitoso. */
  warnings: SceneIssue[];
  /** Contador para generar `EditorShop.key` sin estado global (el reducer sigue siendo puro). */
  nextKey: number;
}

export type NudgeDirection = "up" | "down" | "left" | "right";

export type EditorAction =
  | { type: "loadVersion"; version: SceneVersion }
  | { type: "addShop"; name: string }
  | { type: "renameShop"; shopIndex: number; name: string }
  | { type: "removeShop"; shopIndex: number }
  | { type: "select"; selection: EditorSelection | null }
  | { type: "startDrawing"; shopIndex: number; element: EditorElement }
  | { type: "addPoint"; point: Point }
  | { type: "finishDrawing" }
  | { type: "cancelDrawing" }
  | { type: "moveVertex"; shopIndex: number; element: EditorElement; vertexIndex: number; point: Point }
  | {
      type: "nudgeVertex";
      shopIndex: number;
      element: EditorElement;
      vertexIndex: number;
      direction: NudgeDirection;
      large: boolean;
    }
  | { type: "deleteVertex"; shopIndex: number; element: EditorElement; vertexIndex: number }
  | { type: "deleteElement"; shopIndex: number; element: EditorElement }
  | { type: "setZoneRole"; shopIndex: number; from: ZoneRole; to: ZoneRole }
  | { type: "setEntryDirection"; shopIndex: number; direction: EntryDirection }
  | { type: "moveElementToShop"; from: number; element: EditorElement; to: number }
  | { type: "saveSucceeded"; version: SceneVersion; warnings: SceneIssue[] }
  | { type: "saveFailed"; errors: SceneIssue[] };

const ZONE_ROLES: readonly ZoneRole[] = ["front", "interior", "showcase"];

const MIN_ZONE_VERTICES = 3;
const NUDGE_SMALL = 1;
const NUDGE_LARGE = 10;

export function createEditorState({
  frameWidth,
  frameHeight,
}: {
  frameWidth: number;
  frameHeight: number;
}): EditorState {
  return {
    frameWidth,
    frameHeight,
    baseVersionId: null,
    shops: [],
    selection: null,
    drawing: null,
    isDirty: false,
    aspectMismatch: false,
    issues: [],
    warnings: [],
    nextKey: 1,
  };
}

// --- Ayudantes -----------------------------------------------------------------------

function shopKey(n: number): string {
  return `shop-${n}`;
}

function zoneRoleOf(element: EditorElement): ZoneRole | null {
  return element === "entry_line" ? null : (element.slice("zone:".length) as ZoneRole);
}

function hasElement(shop: EditorShop, element: EditorElement): boolean {
  const role = zoneRoleOf(element);
  return role === null ? shop.entry_line !== null : shop.zones[role] !== undefined;
}

/** Vértices del elemento (una línea son sus dos extremos); `null` si el local no lo tiene. */
function elementPoints(shop: EditorShop, element: EditorElement): Point[] | null {
  const role = zoneRoleOf(element);
  if (role === null) {
    return shop.entry_line === null ? null : [shop.entry_line.start, shop.entry_line.end];
  }
  return shop.zones[role] ?? null;
}

function withElementPoints(shop: EditorShop, element: EditorElement, points: Point[]): EditorShop {
  const role = zoneRoleOf(element);
  if (role === null) {
    if (shop.entry_line === null) return shop;
    return { ...shop, entry_line: { ...shop.entry_line, start: points[0], end: points[1] } };
  }
  return { ...shop, zones: { ...shop.zones, [role]: points } };
}

function withoutElement(shop: EditorShop, element: EditorElement): EditorShop {
  const role = zoneRoleOf(element);
  if (role === null) return { ...shop, entry_line: null };
  const zones = { ...shop.zones };
  delete zones[role];
  return { ...shop, zones };
}

function replaceShop(shops: EditorShop[], index: number, shop: EditorShop): EditorShop[] {
  return shops.map((current, i) => (i === index ? shop : current));
}

function isValidShopIndex(state: EditorState, index: number): boolean {
  return Number.isInteger(index) && index >= 0 && index < state.shops.length;
}

function clampPoint(state: EditorState, point: Point): Point {
  return clampToFrame(point, state.frameWidth, state.frameHeight);
}

/** Borra los errores que ya no describen el dibujo (ver "Limpieza de errores al editar"). */
function withoutIssuesOf(
  issues: SceneIssue[],
  shopIndex: number,
  element: SceneIssueElement,
): SceneIssue[] {
  return issues.filter((item) => !(item.shop_index === shopIndex && item.element === element));
}

/** Aplica un cambio de `shops`: marca `isDirty` y borra los errores del elemento editado. */
function edited(
  state: EditorState,
  changes: Partial<EditorState>,
  cleared: { shopIndex: number; element: SceneIssueElement } | null,
): EditorState {
  const issues = changes.issues ?? state.issues;
  return {
    ...state,
    ...changes,
    isDirty: true,
    issues: cleared === null ? issues : withoutIssuesOf(issues, cleared.shopIndex, cleared.element),
  };
}

function shopFromVersion(
  shop: SceneVersion["shops"][number],
  key: string,
  frameWidth: number,
  frameHeight: number,
): EditorShop {
  const toFrame = (point: Point): Point =>
    clampToFrame(normalizedToFrame(point, frameWidth, frameHeight), frameWidth, frameHeight);
  const zones: Zones = {};
  for (const role of ZONE_ROLES) {
    const points = shop.zones[role];
    if (points !== undefined) zones[role] = points.map(toFrame);
  }
  return {
    key,
    shop_id: shop.shop_id,
    name: shop.name,
    zones,
    entry_line: shop.entry_line
      ? {
          start: toFrame(shop.entry_line.start),
          end: toFrame(shop.entry_line.end),
          entry_direction: shop.entry_line.entry_direction,
        }
      : null,
  };
}

function nudgeDelta(direction: NudgeDirection, step: number): Point {
  switch (direction) {
    case "up":
      return [0, -step];
    case "down":
      return [0, step];
    case "left":
      return [-step, 0];
    case "right":
      return [step, 0];
  }
}

// --- Reducer -------------------------------------------------------------------------

export function editorReducer(state: EditorState, action: EditorAction): EditorState {
  switch (action.type) {
    case "loadVersion": {
      const { version } = action;
      const shops = version.shops.map((shop, i) =>
        shopFromVersion(shop, shopKey(state.nextKey + i), state.frameWidth, state.frameHeight),
      );
      return {
        ...state,
        baseVersionId: version.id,
        shops,
        selection: null,
        drawing: null,
        isDirty: false,
        aspectMismatch: !aspectRatioMatches(
          state.frameWidth,
          state.frameHeight,
          version.frame_width,
          version.frame_height,
        ),
        issues: [],
        warnings: [],
        nextKey: state.nextKey + shops.length,
      };
    }

    case "addShop": {
      if (state.shops.length >= MAX_SHOPS_PER_VERSION) return state;
      const shop: EditorShop = {
        key: shopKey(state.nextKey),
        shop_id: null,
        name: action.name,
        zones: {},
        entry_line: null,
      };
      return edited(
        state,
        {
          shops: [...state.shops, shop],
          selection: { shopIndex: state.shops.length, element: null, vertexIndex: null },
          nextKey: state.nextKey + 1,
        },
        null,
      );
    }

    case "renameShop": {
      if (!isValidShopIndex(state, action.shopIndex)) return state;
      const shop = state.shops[action.shopIndex];
      return edited(
        state,
        { shops: replaceShop(state.shops, action.shopIndex, { ...shop, name: action.name }) },
        { shopIndex: action.shopIndex, element: "shop" },
      );
    }

    case "removeShop": {
      const removed = action.shopIndex;
      if (!isValidShopIndex(state, removed)) return state;
      const shift = (index: number) => (index > removed ? index - 1 : index);
      const { selection, drawing } = state;
      return edited(
        state,
        {
          shops: state.shops.filter((_, i) => i !== removed),
          selection:
            selection === null || selection.shopIndex === removed
              ? null
              : { ...selection, shopIndex: shift(selection.shopIndex) },
          drawing:
            drawing === null || drawing.shopIndex === removed
              ? null
              : { ...drawing, shopIndex: shift(drawing.shopIndex) },
          issues: state.issues
            .filter((item) => item.shop_index !== removed)
            .map((item) =>
              item.shop_index !== null && item.shop_index > removed
                ? { ...item, shop_index: item.shop_index - 1 }
                : item,
            ),
        },
        null,
      );
    }

    case "select":
      return { ...state, selection: action.selection };

    case "startDrawing": {
      if (!isValidShopIndex(state, action.shopIndex)) return state;
      if (hasElement(state.shops[action.shopIndex], action.element)) return state;
      return {
        ...state,
        drawing: { shopIndex: action.shopIndex, element: action.element, points: [] },
      };
    }

    case "addPoint": {
      const { drawing } = state;
      if (drawing === null) return state;
      const point = clampPoint(state, action.point);
      if (drawing.element !== "entry_line" || drawing.points.length === 0) {
        return { ...state, drawing: { ...drawing, points: [...drawing.points, point] } };
      }
      const shop = state.shops[drawing.shopIndex];
      const entryLine: EntryLine = { start: drawing.points[0], end: point, entry_direction: "a_to_b" };
      return edited(
        state,
        {
          shops: replaceShop(state.shops, drawing.shopIndex, { ...shop, entry_line: entryLine }),
          drawing: null,
          selection: { shopIndex: drawing.shopIndex, element: "entry_line", vertexIndex: null },
        },
        null,
      );
    }

    case "finishDrawing": {
      const { drawing } = state;
      if (drawing === null) return state;
      const role = zoneRoleOf(drawing.element);
      if (role === null || drawing.points.length < MIN_ZONE_VERTICES) return state;
      const shop = state.shops[drawing.shopIndex];
      return edited(
        state,
        {
          shops: replaceShop(state.shops, drawing.shopIndex, {
            ...shop,
            zones: { ...shop.zones, [role]: drawing.points },
          }),
          drawing: null,
          selection: { shopIndex: drawing.shopIndex, element: drawing.element, vertexIndex: null },
        },
        null,
      );
    }

    case "cancelDrawing":
      return state.drawing === null ? state : { ...state, drawing: null };

    case "moveVertex":
    case "nudgeVertex": {
      const { shopIndex, element, vertexIndex } = action;
      if (!isValidShopIndex(state, shopIndex)) return state;
      const shop = state.shops[shopIndex];
      const points = elementPoints(shop, element);
      if (points === null || vertexIndex < 0 || vertexIndex >= points.length) return state;
      let target: Point;
      if (action.type === "moveVertex") {
        target = action.point;
      } else {
        const [dx, dy] = nudgeDelta(action.direction, action.large ? NUDGE_LARGE : NUDGE_SMALL);
        target = [points[vertexIndex][0] + dx, points[vertexIndex][1] + dy];
      }
      const moved = points.map((point, i) => (i === vertexIndex ? clampPoint(state, target) : point));
      return edited(
        state,
        { shops: replaceShop(state.shops, shopIndex, withElementPoints(shop, element, moved)) },
        { shopIndex, element },
      );
    }

    case "deleteVertex": {
      const { shopIndex, element, vertexIndex } = action;
      if (!isValidShopIndex(state, shopIndex) || zoneRoleOf(element) === null) return state;
      const shop = state.shops[shopIndex];
      const points = elementPoints(shop, element);
      if (points === null || points.length <= MIN_ZONE_VERTICES) return state;
      if (vertexIndex < 0 || vertexIndex >= points.length) return state;
      const { selection } = state;
      const pointsAtElement =
        selection !== null &&
        selection.shopIndex === shopIndex &&
        selection.element === element &&
        selection.vertexIndex !== null;
      let nextSelection = selection;
      if (pointsAtElement && selection.vertexIndex !== null) {
        if (selection.vertexIndex === vertexIndex) {
          nextSelection = { ...selection, vertexIndex: null };
        } else if (selection.vertexIndex > vertexIndex) {
          nextSelection = { ...selection, vertexIndex: selection.vertexIndex - 1 };
        }
      }
      return edited(
        state,
        {
          shops: replaceShop(
            state.shops,
            shopIndex,
            withElementPoints(
              shop,
              element,
              points.filter((_, i) => i !== vertexIndex),
            ),
          ),
          selection: nextSelection,
        },
        { shopIndex, element },
      );
    }

    case "deleteElement": {
      const { shopIndex, element } = action;
      if (!isValidShopIndex(state, shopIndex)) return state;
      const shop = state.shops[shopIndex];
      if (!hasElement(shop, element)) return state;
      const { selection } = state;
      return edited(
        state,
        {
          shops: replaceShop(state.shops, shopIndex, withoutElement(shop, element)),
          selection:
            selection !== null && selection.shopIndex === shopIndex && selection.element === element
              ? null
              : selection,
        },
        { shopIndex, element },
      );
    }

    case "setZoneRole": {
      const { shopIndex, from, to } = action;
      if (!isValidShopIndex(state, shopIndex) || from === to) return state;
      const shop = state.shops[shopIndex];
      const points = shop.zones[from];
      if (points === undefined || shop.zones[to] !== undefined) return state;
      const zones = { ...shop.zones, [to]: points };
      delete zones[from];
      const fromElement: EditorElement = `zone:${from}`;
      const { selection, drawing } = state;
      return edited(
        state,
        {
          shops: replaceShop(state.shops, shopIndex, { ...shop, zones }),
          selection:
            selection !== null && selection.shopIndex === shopIndex && selection.element === fromElement
              ? { ...selection, element: `zone:${to}` }
              : selection,
          // Un dibujo en curso del rol `to` en este local quedaría duplicado al cerrarse.
          drawing:
            drawing !== null && drawing.shopIndex === shopIndex && drawing.element === `zone:${to}`
              ? null
              : drawing,
        },
        { shopIndex, element: fromElement },
      );
    }

    case "setEntryDirection": {
      const { shopIndex, direction } = action;
      if (!isValidShopIndex(state, shopIndex)) return state;
      const shop = state.shops[shopIndex];
      if (shop.entry_line === null) return state;
      return edited(
        state,
        {
          shops: replaceShop(state.shops, shopIndex, {
            ...shop,
            entry_line: { ...shop.entry_line, entry_direction: direction },
          }),
        },
        { shopIndex, element: "entry_line" },
      );
    }

    case "moveElementToShop": {
      const { from, element, to } = action;
      if (from === to || !isValidShopIndex(state, from) || !isValidShopIndex(state, to)) return state;
      const source = state.shops[from];
      const target = state.shops[to];
      if (!hasElement(source, element) || hasElement(target, element)) return state;
      const role = zoneRoleOf(element);
      const movedTarget: EditorShop =
        role === null
          ? { ...target, entry_line: source.entry_line }
          : { ...target, zones: { ...target.zones, [role]: source.zones[role] } };
      const shops = state.shops.map((shop, i) => {
        if (i === from) return withoutElement(source, element);
        if (i === to) return movedTarget;
        return shop;
      });
      const { drawing } = state;
      return edited(
        state,
        {
          shops,
          selection: { shopIndex: to, element, vertexIndex: null },
          // Un dibujo en curso de ese elemento en el destino quedaría duplicado al cerrarse.
          drawing:
            drawing !== null && drawing.shopIndex === to && drawing.element === element ? null : drawing,
        },
        { shopIndex: from, element },
      );
    }

    case "saveSucceeded": {
      const { version, warnings } = action;
      return {
        ...state,
        baseVersionId: version.id,
        shops: state.shops.map((shop, i) => {
          const saved = version.shops[i];
          return saved === undefined ? shop : { ...shop, shop_id: saved.shop_id };
        }),
        isDirty: false,
        aspectMismatch: false,
        issues: [],
        warnings,
      };
    }

    case "saveFailed":
      return { ...state, issues: action.errors };
  }
}

// --- Selectores ----------------------------------------------------------------------

/** `shopIndex = null` devuelve los errores de la versión; sin `element`, todos los del local. */
export function issuesFor(
  state: EditorState,
  shopIndex: number | null,
  element?: SceneIssueElement,
): SceneIssue[] {
  return state.issues.filter(
    (item) => item.shop_index === shopIndex && (element === undefined || item.element === element),
  );
}

export function hasIssue(state: EditorState, shopIndex: number, element: SceneIssueElement): boolean {
  return state.issues.some((item) => item.shop_index === shopIndex && item.element === element);
}

/** Roles sin zona en ese local, en el orden `front`, `interior`, `showcase`. */
export function availableZoneRoles(state: EditorState, shopIndex: number): ZoneRole[] {
  const shop = state.shops[shopIndex];
  if (shop === undefined) return [];
  return ZONE_ROLES.filter((role) => shop.zones[role] === undefined);
}

// --- Payload de guardado ---------------------------------------------------------------

/** Única función que normaliza; envía solo lo confirmado (nunca el dibujo en curso). */
export function toSceneVersionCreate(
  state: EditorState,
  referenceSessionId: string,
  frameWidth: number,
  frameHeight: number,
): SceneVersionCreate {
  const normalize = (point: Point): Point => frameToNormalized(point, frameWidth, frameHeight);
  const shops: ShopInput[] = state.shops.map((shop) => {
    const zones: Zones = {};
    for (const role of ZONE_ROLES) {
      const points = shop.zones[role];
      if (points !== undefined) zones[role] = points.map(normalize);
    }
    return {
      shop_id: shop.shop_id,
      name: shop.name,
      zones,
      entry_line:
        shop.entry_line === null
          ? null
          : {
              start: normalize(shop.entry_line.start),
              end: normalize(shop.entry_line.end),
              entry_direction: shop.entry_line.entry_direction,
            },
    };
  });
  return {
    reference_session_id: referenceSessionId,
    base_version_id: state.baseVersionId,
    shops,
  };
}
