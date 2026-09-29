import type { EntryDirection, Point } from "../types/scene";

/**
 * Conversión de coordenadas del editor de escenas (FR-033).
 *
 * El estado del editor vive en píxeles del frame de referencia (coordenadas de imagen, y crece
 * hacia abajo); solo se normaliza a [0, 1] al guardar.
 */

/** Largo total de la flecha de entrada, en píxeles del frame. */
export const ENTRY_ARROW_LENGTH = 60;

/** Decimales del normalizado (paridad con `normalize` del backend, R11). */
const NORMALIZED_DECIMALS = 6;
const NORMALIZED_FACTOR = 10 ** NORMALIZED_DECIMALS;

/**
 * Pantalla → píxeles del frame. Lee la CTM en cada llamada (redimensionar no requiere estado) y
 * aplica su inversa a mano con los campos `a`–`f`: `createSVGPoint`/`matrixTransform` no existen
 * en jsdom. No limita al frame (ver `clampToFrame`). `null` si el SVG no está renderizado.
 */
export function screenToFrame(svg: SVGSVGElement, clientX: number, clientY: number): Point | null {
  const ctm = svg.getScreenCTM();
  if (ctm === null) return null;
  const { a, b, c, d, e, f } = ctm.inverse();
  return [a * clientX + c * clientY + e, b * clientX + d * clientY + f];
}

function roundNormalized(value: number): number {
  return Math.round(value * NORMALIZED_FACTOR) / NORMALIZED_FACTOR;
}

export function frameToNormalized(point: Point, frameWidth: number, frameHeight: number): Point {
  return [roundNormalized(point[0] / frameWidth), roundNormalized(point[1] / frameHeight)];
}

export function normalizedToFrame(point: Point, frameWidth: number, frameHeight: number): Point {
  return [point[0] * frameWidth, point[1] * frameHeight];
}

function clamp(value: number, max: number): number {
  return Math.min(Math.max(value, 0), max);
}

/** Limita a `[0, W] × [0, H]` (intervalo cerrado). */
export function clampToFrame(point: Point, frameWidth: number, frameHeight: number): Point {
  return [clamp(point[0], frameWidth), clamp(point[1], frameHeight)];
}

/** Misma fórmula que `aspect_ratio_matches` del backend: `|(wv/hv) / (wf/hf) − 1| <= tol`. */
export function aspectRatioMatches(
  videoWidth: number,
  videoHeight: number,
  frameWidth: number,
  frameHeight: number,
  tol = 0.01,
): boolean {
  return Math.abs(videoWidth / videoHeight / (frameWidth / frameHeight) - 1) <= tol;
}

/**
 * Punto medio y normal unitaria hacia el lado A (`cross > 0`, R11). Para `(dx, dy)` la normal
 * `(-dy, dx)` da `cross = dx² + dy² > 0`. `null` si la línea tiene largo 0.
 */
function midpointAndSideANormal(start: Point, end: Point): { mid: Point; normal: Point } | null {
  const dx = end[0] - start[0];
  const dy = end[1] - start[1];
  const length = Math.hypot(dx, dy);
  if (length === 0) return null;
  return {
    mid: [(start[0] + end[0]) / 2, (start[1] + end[1]) / 2],
    normal: [-dy / length, dx / length],
  };
}

function alongNormal(mid: Point, normal: Point, distance: number): Point {
  return [mid[0] + normal[0] * distance, mid[1] + normal[1] * distance];
}

/** Posiciones de las etiquetas "A" y "B" a `offset` px del punto medio, sobre la normal. */
export function lineSideLabelPositions(
  start: Point,
  end: Point,
  offset = 20,
): { A: Point; B: Point } | null {
  const geometry = midpointAndSideANormal(start, end);
  if (geometry === null) return null;
  return {
    A: alongNormal(geometry.mid, geometry.normal, offset),
    B: alongNormal(geometry.mid, geometry.normal, -offset),
  };
}

/**
 * Flecha de entrada sobre la normal, centrada en el punto medio de la línea: con `a_to_b` va del
 * lado A al B; con `b_to_a`, al revés. `null` si la línea tiene largo 0.
 */
export function entryArrow(
  start: Point,
  end: Point,
  direction: EntryDirection,
): { from: Point; to: Point } | null {
  const geometry = midpointAndSideANormal(start, end);
  if (geometry === null) return null;
  const half = ENTRY_ARROW_LENGTH / 2;
  const sideA = alongNormal(geometry.mid, geometry.normal, half);
  const sideB = alongNormal(geometry.mid, geometry.normal, -half);
  return direction === "a_to_b" ? { from: sideA, to: sideB } : { from: sideB, to: sideA };
}
