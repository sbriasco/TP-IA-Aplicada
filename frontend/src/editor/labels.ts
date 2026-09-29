import type { SceneIssueElement, ZoneRole } from "../types/scene";
import type { EditorElement } from "./editorState";

/** Nombres visibles de los roles de zona (opciones de los `<select>`). */
export const ZONE_ROLE_OPTION: Record<ZoneRole, string> = {
  front: "Frontal",
  interior: "Interior",
  showcase: "Vidriera",
};

const ELEMENT_NAME: Record<EditorElement, string> = {
  "zone:front": "zona frontal",
  "zone:interior": "zona interior",
  "zone:showcase": "zona de vidriera",
  entry_line: "línea de entrada",
};

/** "zona frontal", "línea de entrada"… en minúscula, para componer nombres accesibles. */
export function elementName(element: EditorElement): string {
  return ELEMENT_NAME[element];
}

/** Igual que `elementName` con mayúscula inicial ("Zona frontal"). */
export function elementTitle(element: EditorElement): string {
  const name = ELEMENT_NAME[element];
  return name.charAt(0).toUpperCase() + name.slice(1);
}

/** Etiqueta de cualquier elemento de un error de la API, incluidos "Local" y "Versión". */
export function issueElementTitle(element: SceneIssueElement): string {
  if (element === "version") return "Versión";
  if (element === "shop") return "Local";
  return elementTitle(element);
}

/** Nombre de un local para mostrar; si está vacío, usa su posición. */
export function shopDisplayName(name: string, index: number): string {
  return name.trim() === "" ? `Local ${index + 1} (sin nombre)` : name;
}
