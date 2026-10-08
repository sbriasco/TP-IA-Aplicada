import type { EntryDirection, Point } from "../types/scene";

/** Misma franja normalizada que el contador del backend. */
export const LINE_SIDE_BAND = 0.004;

export interface ProbeReading {
  label: "Entrada" | "Salida" | "Sin cruce" | "Sobre la línea" | "Sin línea";
  detail: string;
}

function cross(start: Point, end: Point, point: Point): number {
  return (end[0] - start[0]) * (point[1] - start[1]) - (end[1] - start[1]) * (point[0] - start[0]);
}

function footSide(start: Point, end: Point, point: Point): "A" | "B" | null {
  const length = Math.hypot(end[0] - start[0], end[1] - start[1]);
  if (length === 0) return null;
  const value = cross(start, end, point);
  if (Math.abs(value) <= LINE_SIDE_BAND * length) return null;
  return value > 0 ? "A" : "B";
}

function onSegment(start: Point, end: Point, point: Point): boolean {
  return (
    Math.min(start[0], end[0]) <= point[0] && point[0] <= Math.max(start[0], end[0]) &&
    Math.min(start[1], end[1]) <= point[1] && point[1] <= Math.max(start[1], end[1])
  );
}

function segmentsIntersect(p1: Point, p2: Point, q1: Point, q2: Point): boolean {
  const o1 = cross(p1, p2, q1);
  const o2 = cross(p1, p2, q2);
  const o3 = cross(q1, q2, p1);
  const o4 = cross(q1, q2, p2);
  if ((o1 > 0) !== (o2 > 0) && (o3 > 0) !== (o4 > 0)) return true;
  if (o1 === 0 && onSegment(p1, p2, q1)) return true;
  if (o2 === 0 && onSegment(p1, p2, q2)) return true;
  if (o3 === 0 && onSegment(q1, q2, p1)) return true;
  if (o4 === 0 && onSegment(q1, q2, p2)) return true;
  return false;
}

/** Sentido de dos puntos de pies, sin detector. Las coordenadas están normalizadas. */
export function probeCrossing(
  from: Point,
  to: Point,
  lineStart: Point | null,
  lineEnd: Point | null,
  entryDirection: EntryDirection | null,
): ProbeReading {
  if (lineStart === null || lineEnd === null || entryDirection === null) {
    return { label: "Sin línea", detail: "Esta zona no tiene una línea de acceso para probar." };
  }
  const previous = footSide(lineStart, lineEnd, from);
  const current = footSide(lineStart, lineEnd, to);
  if (previous === null || current === null) {
    return {
      label: "Sobre la línea",
      detail: "Un punto queda en la franja de la línea. Hacé clic más separado, de un lado y del otro.",
    };
  }
  if (previous === current || !segmentsIntersect(from, to, lineStart, lineEnd)) {
    return {
      label: "Sin cruce",
      detail: previous === current
        ? "Los dos puntos están del mismo lado. No hay cruce."
        : "La trayectoria pasa junto a la línea, pero no cruza su tramo.",
    };
  }
  const sense = previous === "A" && current === "B" ? "a_to_b" : "b_to_a";
  const entry = sense === entryDirection;
  return {
    label: entry ? "Entrada" : "Salida",
    detail: entry
      ? "Ese recorrido cuenta como entrada con la flecha actual."
      : "Ese recorrido cuenta como salida. Si esperabas una entrada, invertí la flecha.",
  };
}
