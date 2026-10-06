import type { SceneIssueElement, ZoneRole } from "../types/scene";
import type { EditorElement } from "./editorState";

/** Nombres visibles de los roles de zona (opciones de los `<select>`). */
export const ZONE_ROLE_OPTION: Record<ZoneRole, string> = {
  front: "Externa",
  interior: "Interior",
  showcase: "Interés",
};

const ELEMENT_NAME: Record<EditorElement, string> = {
  "zone:front": "área externa",
  "zone:interior": "área interior",
  "zone:showcase": "área de interés",
  entry_line: "línea de entrada",
};

/** "área externa", "línea de entrada"… en minúscula, para componer nombres accesibles. */
export function elementName(element: EditorElement): string {
  return ELEMENT_NAME[element];
}

/** Igual que `elementName` con mayúscula inicial ("Área externa"). */
export function elementTitle(element: EditorElement): string {
  const name = ELEMENT_NAME[element];
  return name.charAt(0).toUpperCase() + name.slice(1);
}

/** Etiqueta de cualquier elemento de un error de la API, incluidos "Local" y "Versión". */
export function issueElementTitle(element: SceneIssueElement): string {
  if (element === "version") return "Versión";
  if (element === "shop") return "Zona de análisis";
  return elementTitle(element);
}

/** Nombre de un local para mostrar; si está vacío, usa su posición. */
export function shopDisplayName(name: string, index: number): string {
  return name.trim() === "" ? `Zona ${index + 1} (sin nombre)` : name;
}
