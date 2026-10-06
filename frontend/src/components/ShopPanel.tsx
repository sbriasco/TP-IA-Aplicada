import { useId, useState, type Dispatch } from "react";

import {
  availableZoneRoles,
  type EditorAction,
  type EditorElement,
  type EditorShop,
  type EditorState,
} from "../editor/editorState";
import { elementName, elementTitle, shopDisplayName, ZONE_ROLE_OPTION } from "../editor/labels";
import { MAX_SHOPS_PER_VERSION, type Point, type ZoneRole } from "../types/scene";

interface ShopPanelProps {
  state: EditorState;
  dispatch: Dispatch<EditorAction>;
}

const ZONE_ROLES: readonly ZoneRole[] = ["front", "interior", "showcase"];
const MIN_ZONE_VERTICES = 3;
const KEYBOARD_POINTS = 8;

/** Elementos existentes de un local, en el orden del `<select>` "Elemento". */
function elementsOf(shop: EditorShop): EditorElement[] {
  const elements: EditorElement[] = ZONE_ROLES.filter((role) => shop.zones[role] !== undefined).map(
    (role) => `zone:${role}` as const,
  );
  if (shop.entry_line !== null) elements.push("entry_line");
  return elements;
}

function hasElement(shop: EditorShop, element: EditorElement): boolean {
  return element === "entry_line"
    ? shop.entry_line !== null
    : shop.zones[element.slice("zone:".length) as ZoneRole] !== undefined;
}

function elementPointCount(shop: EditorShop, element: EditorElement): number {
  if (element === "entry_line") return shop.entry_line === null ? 0 : 2;
  return shop.zones[element.slice("zone:".length) as ZoneRole]?.length ?? 0;
}

/**
 * Punto para "Agregar vértice" sin puntero: sobre un círculo alrededor del centro del frame, así
 * los puntos sucesivos forman un polígono válido que después se ajusta con las flechas.
 */
function keyboardPoint(state: EditorState, index: number): Point {
  const radius = Math.min(state.frameWidth, state.frameHeight) / 6;
  const angle = -Math.PI / 2 + (index % KEYBOARD_POINTS) * ((2 * Math.PI) / KEYBOARD_POINTS);
  return [
    state.frameWidth / 2 + radius * Math.cos(angle),
    state.frameHeight / 2 + radius * Math.sin(angle),
  ];
}

/** Locales y sus elementos con controles nativos (T043, FR-031, FR-036). */
export function ShopPanel({ state, dispatch }: ShopPanelProps) {
  const id = useId();
  const [newRole, setNewRole] = useState<ZoneRole | "">("");
  const [moveTarget, setMoveTarget] = useState("");

  const { shops, selection, drawing } = state;
  const shopIndex = selection !== null && shops[selection.shopIndex] !== undefined ? selection.shopIndex : null;
  const shop = shopIndex === null ? null : shops[shopIndex];
  const element = shop !== null && selection !== null ? selection.element : null;

  const roles = shopIndex === null ? [] : availableZoneRoles(state, shopIndex);
  const role: ZoneRole | "" = newRole !== "" && roles.includes(newRole) ? newRole : (roles.at(0) ?? "");
  const targets =
    shopIndex === null || element === null
      ? []
      : shops
          .map((candidate, index) => ({ candidate, index }))
          .filter(({ candidate, index }) => index !== shopIndex && !hasElement(candidate, element));
  const target = targets.some(({ index }) => String(index) === moveTarget)
    ? moveTarget
    : String(targets[0]?.index ?? "");

  function select(index: number | null, selected: EditorElement | null = null) {
    dispatch({
      type: "select",
      selection: index === null ? null : { shopIndex: index, element: selected, vertexIndex: null },
    });
  }

  let drawingSection = null;
  if (drawing !== null) {
    const drawingShop = shops[drawing.shopIndex];
    const isLine = drawing.element === "entry_line";
    const count = drawing.points.length;
    drawingSection = (
      <section aria-labelledby={`${id}-drawing`}>
        <h3 id={`${id}-drawing`}>Dibujo en curso</h3>
        <p role="status">
          Dibujando {elementName(drawing.element)} de{" "}
          {drawingShop === undefined ? "" : shopDisplayName(drawingShop.name, drawing.shopIndex)}:{" "}
          {isLine
            ? count === 0
              ? "hacé clic sobre el frame en el primer extremo."
              : "hacé clic sobre el frame en el segundo extremo."
            : `${count} ${count === 1 ? "vértice" : "vértices"}. Hacé clic sobre el frame para agregar vértices y cerrá el polígono con el botón o con Enter.`}
        </p>
        <button
          type="button"
          onClick={() => dispatch({ type: "addPoint", point: keyboardPoint(state, count) })}
        >
          Agregar vértice
        </button>{" "}
        {!isLine && (
          <>
            <button
              type="button"
              disabled={count < MIN_ZONE_VERTICES}
              onClick={() => dispatch({ type: "finishDrawing" })}
            >
              Cerrar polígono
            </button>{" "}
          </>
        )}
        <button type="button" onClick={() => dispatch({ type: "cancelDrawing" })}>
          Cancelar dibujo
        </button>
        <p>
          <small>
            "Agregar vértice" ubica un punto cerca del centro del frame, para dibujar sin puntero; después
            se mueve con las flechas (Shift: 10 px).
          </small>
        </p>
      </section>
    );
  }

  let elementSection = null;
  if (shop !== null && shopIndex !== null && element !== null && hasElement(shop, element)) {
    const zoneRole = element === "entry_line" ? null : (element.slice("zone:".length) as ZoneRole);
    const vertexIndex = selection?.vertexIndex ?? null;
    const canDeleteVertex =
      zoneRole !== null && vertexIndex !== null && elementPointCount(shop, element) > MIN_ZONE_VERTICES;
    elementSection = (
      <section aria-labelledby={`${id}-element`}>
        <h3 id={`${id}-element`}>{elementTitle(element)}</h3>
        {zoneRole !== null && (
          <p>
            <label htmlFor={`${id}-zone-role`}>Tipo de área</label>{" "}
            <select
              id={`${id}-zone-role`}
              value={zoneRole}
              onChange={(event) =>
                dispatch({
                  type: "setZoneRole",
                  shopIndex,
                  from: zoneRole,
                  to: event.target.value as ZoneRole,
                })
              }
            >
              {[zoneRole, ...roles]
                .sort((a, b) => ZONE_ROLES.indexOf(a) - ZONE_ROLES.indexOf(b))
                .map((option) => (
                  <option key={option} value={option}>
                    {ZONE_ROLE_OPTION[option]}
                  </option>
                ))}
            </select>
          </p>
        )}
        <p>
          {vertexIndex === null
            ? "Elegí un vértice sobre el frame (clic o Tab) para moverlo con las flechas."
            : `Vértice ${vertexIndex + 1} seleccionado: movelo con las flechas (Shift: 10 px).`}
        </p>
        {zoneRole !== null && (
          <>
            <button
              type="button"
              disabled={!canDeleteVertex}
              onClick={() => {
                if (vertexIndex !== null) {
                  dispatch({ type: "deleteVertex", shopIndex, element, vertexIndex });
                }
              }}
            >
              Eliminar vértice
            </button>{" "}
          </>
        )}
        <button type="button" onClick={() => dispatch({ type: "deleteElement", shopIndex, element })}>
          Eliminar elemento
        </button>
        {targets.length === 0 ? (
          <p>Ninguna otra zona puede recibir este elemento.</p>
        ) : (
          <p>
            <label htmlFor={`${id}-move`}>Mover a zona</label>{" "}
            <select id={`${id}-move`} value={target} onChange={(event) => setMoveTarget(event.target.value)}>
              {targets.map(({ candidate, index }) => (
                <option key={candidate.key} value={String(index)}>
                  {shopDisplayName(candidate.name, index)}
                </option>
              ))}
            </select>{" "}
            <button
              type="button"
              onClick={() =>
                dispatch({ type: "moveElementToShop", from: shopIndex, element, to: Number(target) })
              }
            >
              Mover elemento
            </button>
          </p>
        )}
      </section>
    );
  }

  return (
    <section aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`}>Zonas de análisis</h2>
      <p>
        <button
          type="button"
          disabled={shops.length >= MAX_SHOPS_PER_VERSION}
          onClick={() => dispatch({ type: "addShop", name: `Zona ${shops.length + 1}` })}
        >
          Agregar zona
        </button>
      </p>
      {shops.length > 0 && (
        <p>
          <label htmlFor={`${id}-shop`}>Zona en edición</label>{" "}
          <select
            id={`${id}-shop`}
            value={shopIndex === null ? "" : String(shopIndex)}
            onChange={(event) => select(event.target.value === "" ? null : Number(event.target.value))}
          >
            <option value="">Elegí una zona</option>
            {shops.map((item, index) => (
              <option key={item.key} value={String(index)}>
                {shopDisplayName(item.name, index)}
              </option>
            ))}
          </select>
        </p>
      )}

      {shop !== null && shopIndex !== null && (
        <>
          <p>
            <label htmlFor={`${id}-name`}>Nombre de la zona</label>{" "}
            <input
              id={`${id}-name`}
              type="text"
              value={shop.name}
              onChange={(event) => dispatch({ type: "renameShop", shopIndex, name: event.target.value })}
            />{" "}
            <button type="button" onClick={() => dispatch({ type: "removeShop", shopIndex })}>
              Quitar zona de esta versión
            </button>
          </p>
          <p>
            <label htmlFor={`${id}-new-role`}>Tipo de área nueva</label>{" "}
            <select
              id={`${id}-new-role`}
              value={role}
              disabled={roles.length === 0}
              onChange={(event) => setNewRole(event.target.value as ZoneRole)}
            >
              {roles.length === 0 && <option value="">Todas las áreas ya están dibujadas</option>}
              {roles.map((option) => (
                <option key={option} value={option}>
                  {ZONE_ROLE_OPTION[option]}
                </option>
              ))}
            </select>{" "}
            <button
              type="button"
              disabled={role === ""}
              onClick={() => {
                if (role === "") return;
                dispatch({ type: "startDrawing", shopIndex, element: `zone:${role}` });
                // La próxima zona (de este u otro local) vuelve a proponer el primer rol libre.
                setNewRole("");
              }}
            >
              Dibujar área
            </button>{" "}
            <button
              type="button"
              disabled={shop.entry_line !== null}
              onClick={() => dispatch({ type: "startDrawing", shopIndex, element: "entry_line" })}
            >
              Crear línea de entrada
            </button>
          </p>
          <p>
            <label htmlFor={`${id}-element-select`}>Elemento</label>{" "}
            <select
              id={`${id}-element-select`}
              value={element ?? ""}
              onChange={(event) =>
                select(shopIndex, event.target.value === "" ? null : (event.target.value as EditorElement))
              }
            >
              <option value="">Ninguno</option>
              {elementsOf(shop).map((option) => (
                <option key={option} value={option}>
                  {elementTitle(option)}
                </option>
              ))}
            </select>
          </p>
        </>
      )}

      {drawingSection}
      {elementSection}
    </section>
  );
}
