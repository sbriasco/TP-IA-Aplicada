import { useId, useState, type Dispatch } from "react";
import { Eye, EyeOff, Trash2, Plus, Layers } from "lucide-react";
import { availableZoneRoles, type EditorAction, type EditorElement, type EditorState } from "../editor/editorState";
import { elementTitle, shopDisplayName, ZONE_ROLE_OPTION } from "../editor/labels";
import { MAX_SHOPS_PER_VERSION, type ZoneRole } from "../types/scene";
import { EntryLineControls } from "./EntryLineControls";

interface SceneLayersProps {
  state: EditorState;
  dispatch: Dispatch<EditorAction>;
  hidden: ReadonlySet<string>;
  toggleVisibility: (key: string) => void;
  onGestureStart?: () => void;
  onGestureEnd?: () => void;
}
const ROLES: readonly ZoneRole[] = ["front", "interior", "showcase"];
const field = "grid gap-2 text-xs";

export function SceneLayers({ state, dispatch, hidden, toggleVisibility, onGestureStart, onGestureEnd }: SceneLayersProps) {
  const id = useId();
  const [newRole, setNewRole] = useState<ZoneRole>("front");
  const index = state.selection?.shopIndex;
  const shop = index === undefined ? undefined : state.shops[index];
  const element = state.selection?.element ?? null;
  const roles = index === undefined ? [] : availableZoneRoles(state, index);
  const drawing = state.drawing;
  const chosenRole = roles.includes(newRole) ? newRole : roles[0];
  const elementsOf = (shopIndex: number): EditorElement[] => {
    const item = state.shops[shopIndex];
    return [...ROLES.filter(role => item.zones[role] !== undefined).map(role => `zone:${role}` as const), ...(item.entry_line ? ["entry_line" as const] : [])];
  };
  function select(shopIndex: number, selected: EditorElement | null = null) {
    dispatch({ type: "select", selection: { shopIndex, element: selected, vertexIndex: null } });
  }
  return <div className="flex min-h-0 flex-col gap-3 text-sm">
    <section aria-labelledby={`${id}-layers`}>
      <div className="mb-2 flex items-center justify-between gap-2"><h2 id={`${id}-layers`} className="!m-0 !text-sm flex items-center gap-2"><Layers size={16} aria-hidden="true" />Zonas configuradas</h2><span className="text-xs text-[var(--fs-muted)]">{state.shops.length}</span></div>
      <div className="grid gap-2">
        {state.shops.map((item, shopIndex) => <div key={item.key} className={`rounded-lg border p-2 ${index === shopIndex ? "border-[var(--fs-accent)] bg-[var(--fs-tint)]" : "border-[var(--fs-line)] bg-[var(--fs-raised)]"}`}>
          <div className="flex min-w-0 items-center gap-2"><span className="h-2 w-2 shrink-0 rounded-full bg-emerald-500" aria-hidden="true" /><button type="button" className="!min-h-8 !border-0 !bg-transparent !p-1 min-w-0 flex-1 !text-left !text-xs truncate" aria-pressed={index === shopIndex} onClick={() => select(shopIndex)}>{shopDisplayName(item.name, shopIndex)}</button><button type="button" className="!min-h-8 !p-1.5" disabled={elementsOf(shopIndex).length === 0} aria-label={`${elementsOf(shopIndex).every(layer => hidden.has(`${item.key}/${layer}`)) ? "Mostrar" : "Ocultar"} zona ${shopDisplayName(item.name, shopIndex)}`} onClick={() => { const allHidden = elementsOf(shopIndex).every(layer => hidden.has(`${item.key}/${layer}`)); elementsOf(shopIndex).forEach(layer => { const key = `${item.key}/${layer}`; if (hidden.has(key) === allHidden) toggleVisibility(key); }); }}>{elementsOf(shopIndex).length > 0 && elementsOf(shopIndex).every(layer => hidden.has(`${item.key}/${layer}`)) ? <EyeOff size={14} aria-hidden="true" /> : <Eye size={14} aria-hidden="true" />}</button><button type="button" className="!min-h-8 !p-1.5" aria-label={`Eliminar zona ${shopDisplayName(item.name, shopIndex)}`} onClick={() => dispatch({ type: "removeShop", shopIndex })}><Trash2 size={14} aria-hidden="true" /></button></div>
          {elementsOf(shopIndex).map(layer => {
            const key = `${item.key}/${layer}`;
            return <div key={layer} className="mt-1 flex items-center gap-1 pl-3"><span className={`h-1.5 w-1.5 shrink-0 rounded-full ${layer === "entry_line" ? "bg-fuchsia-500" : layer === "zone:front" ? "bg-blue-500" : "bg-emerald-500"}`} aria-hidden="true" /><button type="button" className="!min-h-7 !border-0 !bg-transparent !p-1 flex-1 !text-left !text-xs" aria-pressed={index === shopIndex && element === layer} onClick={() => select(shopIndex, layer)}>{elementTitle(layer)}</button><button type="button" className="!min-h-7 !p-1" aria-label={`${hidden.has(key) ? "Mostrar" : "Ocultar"} ${elementTitle(layer)} de ${item.name}`} aria-pressed={!hidden.has(key)} onClick={() => toggleVisibility(key)}>{hidden.has(key) ? <EyeOff size={14} aria-hidden="true" /> : <Eye size={14} aria-hidden="true" />}</button><button type="button" className="!min-h-7 !p-1" aria-label={`Eliminar ${elementTitle(layer)} de ${item.name}`} onClick={() => dispatch({ type: "deleteElement", shopIndex, element: layer })}><Trash2 size={13} aria-hidden="true" /></button></div>;
          })}
          {elementsOf(shopIndex).length === 0 && <p className="!my-1 pl-5 text-xs text-[var(--fs-muted)]">Sin áreas ni líneas dibujadas</p>}
        </div>)}
        {state.shops.length === 0 && <p className="!m-0 rounded-lg border border-dashed border-[var(--fs-line)] p-4 text-xs leading-5 text-[var(--fs-muted)]">Agregá una zona de análisis para empezar a dibujar sobre el frame.</p>}
      </div>
      <button type="button" className="mt-3 flex w-full items-center justify-center gap-2 !text-xs" disabled={state.shops.length >= MAX_SHOPS_PER_VERSION} onClick={() => dispatch({ type: "addShop", name: `Zona ${state.shops.length + 1}` })}><Plus size={15} aria-hidden="true" />Agregar zona</button>
    </section>
    <section aria-labelledby={`${id}-properties`} className="border-t border-[var(--fs-line)] pt-3">
      {shop && <h2 id={`${id}-properties`} className="!mt-0 !text-sm">Propiedades de la zona seleccionada</h2>}
      {shop && index !== undefined ? <div className="mt-2 grid gap-3">
        <div className={field}><label htmlFor={`${id}-name`}>Nombre de la zona</label><input id={`${id}-name`} value={shop.name} maxLength={120} onFocus={onGestureStart} onBlur={onGestureEnd} onChange={event => dispatch({ type: "renameShop", shopIndex: index, name: event.target.value })} /></div>
        <div className={field}><label htmlFor={`${id}-type`}>Tipo de área</label><select id={`${id}-type`} value={(drawing ? drawing.element === "entry_line" : element === "entry_line") ? "line" : "area"} onChange={event => {
          if (event.target.value === "line") { if (shop.entry_line) select(index, "entry_line"); else dispatch({ type: "startDrawing", shopIndex: index, element: "entry_line" }); }
          else { const existing = elementsOf(index).find(candidate => candidate !== "entry_line"); if (existing) select(index, existing); else if (roles[0]) dispatch({ type: "startDrawing", shopIndex: index, element: `zone:${roles[0]}` }); }
        }}><option value="area">Área de interés</option><option value="line">Línea de cruce</option></select></div>
        {element?.startsWith("zone:") && <div className={field}><label htmlFor={`${id}-role`}>Uso del área</label><select id={`${id}-role`} value={element.slice(5)} onChange={event => dispatch({ type: "setZoneRole", shopIndex: index, from: element.slice(5) as ZoneRole, to: event.target.value as ZoneRole })}>{ROLES.filter(role => element === `zone:${role}` || roles.includes(role)).map(role => <option key={role} value={role}>{ZONE_ROLE_OPTION[role]}</option>)}</select></div>}
        {element === "entry_line" && <EntryLineControls state={state} dispatch={dispatch} compact />}
        {element && <div className={field}><label htmlFor={`${id}-associated`}>Elemento asociado</label><select id={`${id}-associated`} value={index} onChange={event => dispatch({ type: "moveElementToShop", from: index, element, to: Number(event.target.value) })}>{state.shops.map((item, i) => <option key={item.key} value={i} disabled={i !== index && elementsOf(i).includes(element)}>{shopDisplayName(item.name, i)}</option>)}</select></div>}
        <details><summary className="cursor-pointer text-xs text-[var(--fs-accent)]">Agregar áreas y accesos</summary><div className="mt-2 grid gap-2"><label htmlFor={`${id}-new-role`}>Tipo de área nueva</label><select id={`${id}-new-role`} value={chosenRole ?? ""} disabled={roles.length === 0} onChange={event => setNewRole(event.target.value as ZoneRole)}>{roles.map(role => <option key={role} value={role}>{ZONE_ROLE_OPTION[role]}</option>)}</select><button type="button" disabled={!chosenRole} onClick={() => { if (chosenRole) dispatch({ type: "startDrawing", shopIndex: index, element: `zone:${chosenRole}` }); }}>Dibujar área</button><button type="button" disabled={shop.entry_line !== null} onClick={() => dispatch({ type: "startDrawing", shopIndex: index, element: "entry_line" })}>Crear línea de entrada</button></div></details>
      </div> : <p className="text-xs leading-5 text-[var(--fs-muted)]">Seleccioná una zona en la lista o creá una nueva</p>}
      {drawing && <div className="mt-4 rounded-lg border border-[var(--fs-line)] bg-[var(--fs-raised)] p-3"><h3 className="!mt-0 !text-xs">Dibujo en curso</h3><p role="status" className="text-xs">{drawing.points.length} puntos · {elementTitle(drawing.element)}</p><div className="flex flex-wrap gap-2"><button type="button" className="!text-xs" onClick={() => { const angle = -Math.PI / 2 + drawing.points.length * Math.PI / 4; const radius = Math.min(state.frameWidth, state.frameHeight) / 6; dispatch({ type: "addPoint", point: [state.frameWidth / 2 + radius * Math.cos(angle), state.frameHeight / 2 + radius * Math.sin(angle)] }); }}>Agregar vértice</button>{drawing.element !== "entry_line" && <button type="button" className="!text-xs" disabled={drawing.points.length < 3} onClick={() => dispatch({ type: "finishDrawing" })}>Cerrar polígono</button>}<button type="button" className="!text-xs" onClick={() => dispatch({ type: "cancelDrawing" })}>Cancelar dibujo</button></div></div>}
    </section>
  </div>;
}
