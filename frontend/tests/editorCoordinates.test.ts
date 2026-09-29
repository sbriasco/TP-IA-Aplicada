/**
 * Pruebas del módulo de coordenadas del editor de escenas (specs/004, T037 → T040).
 *
 * Contrato que asumen para `src/editor/coordinates.ts`:
 *
 * - Los puntos son `Point = [x, y]` (de `src/types/scene.ts`), en píxeles del frame de
 *   referencia (coordenadas de imagen, y crece hacia abajo) salvo que se diga normalizado.
 * - `screenToFrame(svg, clientX, clientY): Point | null` lee `svg.getScreenCTM()` en cada
 *   llamada (así redimensionar no requiere estado), toma su `.inverse()` y aplica a mano los
 *   campos `a`–`f` de la matriz resultante: `x' = a·x + c·y + e`, `y' = b·x + d·y + f`.
 *   Solo usa `getScreenCTM`, `inverse` y `a`–`f`, que existen tanto en `DOMMatrix` como en
 *   `SVGMatrix`; no usa `createSVGPoint`, `matrixTransform` ni `transformPoint` (jsdom no los
 *   implementa y el stub de estas pruebas no los ofrece). Devuelve `null` si
 *   `getScreenCTM()` devuelve `null` (SVG no renderizado). No limita al frame: para eso está
 *   `clampToFrame`.
 * - `frameToNormalized(point, frameWidth, frameHeight): Point` divide por el tamaño del
 *   frame y redondea a 6 decimales (paridad con `normalize` del backend, R11).
 * - `normalizedToFrame(point, frameWidth, frameHeight): Point` multiplica sin redondear.
 * - `clampToFrame(point, frameWidth, frameHeight): Point` limita a `[0, W] × [0, H]` (cerrado).
 * - `aspectRatioMatches(wv, hv, wf, hf, tol = 0.01): boolean` es
 *   `|(wv / hv) / (wf / hf) − 1| <= tol`, igual que `aspect_ratio_matches` del backend.
 * - `lineSideLabelPositions(start, end, offset = 20): { A: Point; B: Point } | null` ubica cada
 *   etiqueta a `offset` px del punto medio sobre la normal; A es el lado con
 *   `cross = dx·(py − sy) − dy·(px − sx) > 0` (R11).
 * - `entryArrow(start, end, direction): { from: Point; to: Point } | null` es un segmento sobre la
 *   normal que pasa por el punto medio de la línea, simétrico respecto de él: con `a_to_b`
 *   `from` está del lado A y `to` del lado B; con `b_to_a`, al revés. El largo no se fija acá.
 * - Con una línea de largo 0 (el primer clic mientras se dibuja) no hay normal: las dos
 *   funciones devuelven `null` y el editor no dibuja etiquetas ni flecha.
 */
import { describe, expect, it, vi } from "vitest";

import {
  aspectRatioMatches,
  clampToFrame,
  entryArrow,
  frameToNormalized,
  lineSideLabelPositions,
  normalizedToFrame,
  screenToFrame,
} from "../src/editor/coordinates";
import type { Point } from "../src/types/scene";

const FRAME_W = 1920;
const FRAME_H = 1080;

// Caso de experiments/video-tracking-validation/config/scene.example.json (mismo que el backend).
const LINE_START: Point = [500, 850];
const LINE_END: Point = [1400, 850];
const SAMPLE_A: Point = [950, 1000];
const SAMPLE_B: Point = [950, 700];

function cross(start: Point, end: Point, p: Point): number {
  const dx = end[0] - start[0];
  const dy = end[1] - start[1];
  return dx * (p[1] - start[1]) - dy * (p[0] - start[0]);
}

/** Etiquetas de una línea con largo; falla la prueba si la función devuelve `null`. */
function labelsOf(...args: Parameters<typeof lineSideLabelPositions>): { A: Point; B: Point } {
  const labels = lineSideLabelPositions(...args);
  if (labels === null) throw new Error("lineSideLabelPositions devolvió null");
  return labels;
}

/** Flecha de una línea con largo; falla la prueba si la función devuelve `null`. */
function arrowOf(...args: Parameters<typeof entryArrow>): { from: Point; to: Point } {
  const arrow = entryArrow(...args);
  if (arrow === null) throw new Error("entryArrow devolvió null");
  return arrow;
}

function distance(p: Point, q: Point): number {
  return Math.hypot(p[0] - q[0], p[1] - q[1]);
}

function midpoint(p: Point, q: Point): Point {
  return [(p[0] + q[0]) / 2, (p[1] + q[1]) / 2];
}

function hasAtMostSixDecimals(value: number): boolean {
  return Number(value.toFixed(6)) === value;
}

// --- Stub mínimo de DOMMatrix/SVGMatrix -------------------------------------------

type MatrixStub = {
  a: number;
  b: number;
  c: number;
  d: number;
  e: number;
  f: number;
  inverse: () => MatrixStub;
};

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
      return matrix(
        d / det,
        -b / det,
        -c / det,
        a / det,
        (c * f - d * e) / det,
        (b * e - a * f) / det,
      );
    },
  };
}

/**
 * CTM de un `<svg viewBox="0 0 W H" preserveAspectRatio="xMidYMid meet">` de
 * `boxW × boxH` px de pantalla ubicado en (`left`, `top`) del viewport.
 */
function meetCtm(boxW: number, boxH: number, left = 0, top = 0): MatrixStub {
  const scale = Math.min(boxW / FRAME_W, boxH / FRAME_H);
  const offsetX = (boxW - FRAME_W * scale) / 2;
  const offsetY = (boxH - FRAME_H * scale) / 2;
  return matrix(scale, 0, 0, scale, left + offsetX, top + offsetY);
}

function fakeSvg(getCtm: () => MatrixStub | null): SVGSVGElement {
  return { getScreenCTM: vi.fn(getCtm) } as unknown as SVGSVGElement;
}

/** Posición en pantalla de un punto del frame según la CTM (sentido directo). */
function toScreen(ctm: MatrixStub, p: Point): [number, number] {
  return [ctm.a * p[0] + ctm.c * p[1] + ctm.e, ctm.b * p[0] + ctm.d * p[1] + ctm.f];
}

// --- Pantalla → frame --------------------------------------------------------------

describe("screenToFrame", () => {
  it("invierte la escala y el letterbox vertical de xMidYMid meet", () => {
    // 1920×1080 en 800×600: escala = min(800/1920, 600/1080) = 5/12, alto dibujado 450,
    // franja de 75 px arriba y abajo; el SVG está en (10, 20) del viewport.
    const ctm = meetCtm(800, 600, 10, 20);
    expect(ctm.a).toBeCloseTo(5 / 12, 12);
    expect(ctm.e).toBeCloseTo(10, 12);
    expect(ctm.f).toBeCloseTo(20 + 75, 12);
    const svg = fakeSvg(() => ctm);

    const [clientX, clientY] = toScreen(ctm, SAMPLE_A);
    const result = screenToFrame(svg, clientX, clientY);

    expect(result).not.toBeNull();
    expect(result![0]).toBeCloseTo(950, 6);
    expect(result![1]).toBeCloseTo(1000, 6);
    expect(svg.getScreenCTM).toHaveBeenCalled();
  });

  it("mapea las esquinas de la imagen dibujada a las del frame", () => {
    const svg = fakeSvg(() => meetCtm(800, 600, 10, 20));

    const topLeft = screenToFrame(svg, 10, 95);
    const bottomRight = screenToFrame(svg, 810, 545);

    expect(topLeft![0]).toBeCloseTo(0, 6);
    expect(topLeft![1]).toBeCloseTo(0, 6);
    expect(bottomRight![0]).toBeCloseTo(FRAME_W, 6);
    expect(bottomRight![1]).toBeCloseTo(FRAME_H, 6);
  });

  it("invierte también el pillarbox horizontal de un contenedor ancho", () => {
    // 1920×1080 en 1600×450: escala = 450/1080, ancho dibujado 800, franja de 400 px a cada lado.
    const ctm = meetCtm(1600, 450);
    expect(ctm.e).toBeCloseTo(400, 12);
    expect(ctm.f).toBeCloseTo(0, 12);
    const svg = fakeSvg(() => ctm);

    const [clientX, clientY] = toScreen(ctm, [1234, 567]);
    const result = screenToFrame(svg, clientX, clientY);

    expect(result![0]).toBeCloseTo(1234, 6);
    expect(result![1]).toBeCloseTo(567, 6);
  });

  it("no limita al frame: un clic en la franja del letterbox cae fuera", () => {
    const svg = fakeSvg(() => meetCtm(800, 600, 10, 20));

    const result = screenToFrame(svg, 410, 30);

    expect(result![1]).toBeLessThan(0);
    expect(clampToFrame(result!, FRAME_W, FRAME_H)[1]).toBe(0);
  });

  it("lee la CTM en cada llamada: el mismo punto del frame sobrevive a tres tamaños", () => {
    const sizes: Array<[number, number, number, number]> = [
      [800, 600, 10, 20],
      [1280, 400, 0, 64],
      [375, 812, 8, 100],
    ];
    let current = meetCtm(...sizes[0]);
    const svg = fakeSvg(() => current);

    for (const size of sizes) {
      current = meetCtm(...size);
      const [clientX, clientY] = toScreen(current, SAMPLE_A);
      const result = screenToFrame(svg, clientX, clientY);
      expect(result![0]).toBeCloseTo(SAMPLE_A[0], 6);
      expect(result![1]).toBeCloseTo(SAMPLE_A[1], 6);
    }
    expect(svg.getScreenCTM).toHaveBeenCalledTimes(sizes.length);
  });

  it("usa la matriz inversa completa, no solo escala y traslación", () => {
    // Matriz con rotación/sesgo: verifica que se usan b y c además de a, d, e y f.
    const ctm = matrix(0.5, 0.2, -0.1, 0.4, 30, 40);
    const svg = fakeSvg(() => ctm);

    const [clientX, clientY] = toScreen(ctm, [700, 300]);
    const result = screenToFrame(svg, clientX, clientY);

    expect(result![0]).toBeCloseTo(700, 6);
    expect(result![1]).toBeCloseTo(300, 6);
  });

  it("devuelve null si el SVG no tiene CTM", () => {
    const svg = fakeSvg(() => null);

    expect(screenToFrame(svg, 100, 100)).toBeNull();
  });
});

// --- Frame ↔ normalizado -----------------------------------------------------------

describe("frameToNormalized / normalizedToFrame", () => {
  it("normaliza redondeando a 6 decimales", () => {
    const result = frameToNormalized(SAMPLE_A, FRAME_W, FRAME_H);

    // 950/1920 = 0.4947916…, 1000/1080 = 0.9259259…
    expect(result).toEqual([0.494792, 0.925926]);
    expect(result.every(hasAtMostSixDecimals)).toBe(true);
  });

  it("normaliza los bordes del frame a 0 y 1", () => {
    expect(frameToNormalized([0, 0], FRAME_W, FRAME_H)).toEqual([0, 0]);
    expect(frameToNormalized([FRAME_W, FRAME_H], FRAME_W, FRAME_H)).toEqual([1, 1]);
  });

  it("redondea cualquier valor a 6 decimales como máximo", () => {
    const result = frameToNormalized([1234.5678, 987.6543], 3840, 2160);

    expect(result.every(hasAtMostSixDecimals)).toBe(true);
    expect(result[0]).toBeCloseTo(1234.5678 / 3840, 6);
    expect(result[1]).toBeCloseTo(987.6543 / 2160, 6);
  });

  it("convierte normalizado a píxeles del frame", () => {
    expect(normalizedToFrame([0.5, 0.25], FRAME_W, FRAME_H)).toEqual([960, 270]);
    expect(normalizedToFrame([1, 1], FRAME_W, FRAME_H)).toEqual([FRAME_W, FRAME_H]);
  });

  it("ida y vuelta frame → normalizado → frame dentro del error de redondeo", () => {
    const point: Point = [1234.5678, 987.6543];

    const back = normalizedToFrame(frameToNormalized(point, 3840, 2160), 3840, 2160);

    // 6 decimales sobre 3840 px: a lo sumo 0,5e-6 · 3840 px de error (igual que el backend).
    expect(Math.abs(back[0] - point[0])).toBeLessThanOrEqual(0.5e-6 * 3840);
    expect(Math.abs(back[1] - point[1])).toBeLessThanOrEqual(0.5e-6 * 2160);
  });

  it("ida y vuelta normalizado → frame → normalizado estable a 1e-6", () => {
    const samples: Point[] = [
      [0.123456, 0.654321],
      [0.494792, 0.925926],
      [0, 1],
      [0.999999, 0.000001],
    ];

    for (const normalized of samples) {
      const once = frameToNormalized(normalizedToFrame(normalized, FRAME_W, FRAME_H), FRAME_W, FRAME_H);
      const twice = frameToNormalized(normalizedToFrame(once, FRAME_W, FRAME_H), FRAME_W, FRAME_H);
      expect(Math.abs(once[0] - normalized[0])).toBeLessThanOrEqual(1e-6);
      expect(Math.abs(once[1] - normalized[1])).toBeLessThanOrEqual(1e-6);
      expect(twice).toEqual(once);
    }
  });
});

// --- clampToFrame --------------------------------------------------------------------

describe("clampToFrame", () => {
  it("deja igual un punto dentro del frame, incluidos los bordes", () => {
    expect(clampToFrame([950, 1000], FRAME_W, FRAME_H)).toEqual([950, 1000]);
    expect(clampToFrame([0, 0], FRAME_W, FRAME_H)).toEqual([0, 0]);
    expect(clampToFrame([FRAME_W, FRAME_H], FRAME_W, FRAME_H)).toEqual([FRAME_W, FRAME_H]);
  });

  it("limita cada eje por separado", () => {
    expect(clampToFrame([-5, 1100], FRAME_W, FRAME_H)).toEqual([0, FRAME_H]);
    expect(clampToFrame([2000, -1], FRAME_W, FRAME_H)).toEqual([FRAME_W, 0]);
    expect(clampToFrame([500, -0.5], FRAME_W, FRAME_H)).toEqual([500, 0]);
  });
});

// --- aspectRatioMatches ------------------------------------------------------------

describe("aspectRatioMatches", () => {
  it.each([
    ["1920x1080 contra 1280x720", 1920, 1080, 1280, 720, true],
    ["misma resolución", 1280, 720, 1280, 720, true],
    ["640x480 contra 1280x720", 640, 480, 1280, 720, false],
    ["dentro del 1 % (0,009375)", 1292, 720, 1280, 720, true],
    ["fuera del 1 % (0,0101…)", 1293, 720, 1280, 720, false],
  ])("%s → %s (mismos casos que el backend)", (_label, wv, hv, wf, hf, expected) => {
    expect(aspectRatioMatches(wv, hv, wf, hf)).toBe(expected);
  });

  it("acepta una tolerancia propia", () => {
    expect(aspectRatioMatches(1293, 720, 1280, 720, 0.02)).toBe(true);
  });

  it("incluye el borde: |ratio − 1| igual a tol coincide (<=)", () => {
    // 3:2 contra 1:1 → |1,5 − 1| = 0,5, exacto en punto flotante.
    expect(aspectRatioMatches(3, 2, 1, 1, 0.5)).toBe(true);
    expect(aspectRatioMatches(3, 2, 1, 1, 0.49)).toBe(false);
    // 3:4 contra 1:1 → |0,75 − 1| = 0,25, también por debajo de 1.
    expect(aspectRatioMatches(3, 4, 1, 1, 0.25)).toBe(true);
  });
});

// --- Etiquetas A/B -----------------------------------------------------------------

describe("lineSideLabelPositions", () => {
  it("ubica A y B a ±20 px de la normal en el punto medio (scene.example.json)", () => {
    // Sanidad de la convención: p = (950, 1000) da cross = +135000 → A.
    expect(cross(LINE_START, LINE_END, SAMPLE_A)).toBe(135000);
    expect(cross(LINE_START, LINE_END, SAMPLE_B)).toBeLessThan(0);

    const { A, B } = labelsOf(LINE_START, LINE_END);

    // Línea horizontal hacia +x: A queda hacia +y (abajo en la imagen), igual que SAMPLE_A.
    expect(A[0]).toBeCloseTo(950, 9);
    expect(A[1]).toBeCloseTo(870, 9);
    expect(B[0]).toBeCloseTo(950, 9);
    expect(B[1]).toBeCloseTo(830, 9);
    expect(cross(LINE_START, LINE_END, A)).toBeGreaterThan(0);
    expect(cross(LINE_START, LINE_END, B)).toBeLessThan(0);
  });

  it("respeta un offset propio", () => {
    const { A, B } = labelsOf(LINE_START, LINE_END, 35);

    expect(A[1]).toBeCloseTo(885, 9);
    expect(B[1]).toBeCloseTo(815, 9);
  });

  it("en una línea diagonal quedan sobre la normal, a la distancia pedida y del lado correcto", () => {
    const start: Point = [100, 200];
    const end: Point = [400, 600];
    const mid = midpoint(start, end);

    const { A, B } = labelsOf(start, end);

    expect(distance(A, mid)).toBeCloseTo(20, 9);
    expect(distance(B, mid)).toBeCloseTo(20, 9);
    // Perpendicular a la línea: producto escalar nulo con (end − start).
    const dx = end[0] - start[0];
    const dy = end[1] - start[1];
    expect(dx * (A[0] - mid[0]) + dy * (A[1] - mid[1])).toBeCloseTo(0, 9);
    expect(dx * (B[0] - mid[0]) + dy * (B[1] - mid[1])).toBeCloseTo(0, 9);
    expect(cross(start, end, A)).toBeGreaterThan(0);
    expect(cross(start, end, B)).toBeLessThan(0);
  });

  it("invertir start y end intercambia los lados", () => {
    const forward = labelsOf(LINE_START, LINE_END);
    const reversed = labelsOf(LINE_END, LINE_START);

    expect(reversed.A[0]).toBeCloseTo(forward.B[0], 9);
    expect(reversed.A[1]).toBeCloseTo(forward.B[1], 9);
    expect(reversed.B[0]).toBeCloseTo(forward.A[0], 9);
    expect(reversed.B[1]).toBeCloseTo(forward.A[1], 9);
  });
});

// --- Flecha de entrada ---------------------------------------------------------------

describe("entryArrow", () => {
  function expectOnNormalThroughMidpoint(start: Point, end: Point, arrow: { from: Point; to: Point }) {
    const mid = midpoint(start, end);
    const arrowMid = midpoint(arrow.from, arrow.to);
    expect(arrowMid[0]).toBeCloseTo(mid[0], 9);
    expect(arrowMid[1]).toBeCloseTo(mid[1], 9);
    const dx = end[0] - start[0];
    const dy = end[1] - start[1];
    expect(dx * (arrow.to[0] - arrow.from[0]) + dy * (arrow.to[1] - arrow.from[1])).toBeCloseTo(0, 9);
    expect(distance(arrow.from, arrow.to)).toBeGreaterThan(0);
  }

  it("con a_to_b va del lado A al lado B (scene.example.json: de abajo hacia arriba)", () => {
    const arrow = arrowOf(LINE_START, LINE_END, "a_to_b");

    expect(cross(LINE_START, LINE_END, arrow.from)).toBeGreaterThan(0);
    expect(cross(LINE_START, LINE_END, arrow.to)).toBeLessThan(0);
    expect(arrow.to[1]).toBeLessThan(arrow.from[1]);
    expectOnNormalThroughMidpoint(LINE_START, LINE_END, arrow);
  });

  it("con b_to_a va del lado B al lado A", () => {
    const arrow = arrowOf(LINE_START, LINE_END, "b_to_a");

    expect(cross(LINE_START, LINE_END, arrow.from)).toBeLessThan(0);
    expect(cross(LINE_START, LINE_END, arrow.to)).toBeGreaterThan(0);
    expect(arrow.to[1]).toBeGreaterThan(arrow.from[1]);
    expectOnNormalThroughMidpoint(LINE_START, LINE_END, arrow);
  });

  it("los dos sentidos son la misma flecha invertida", () => {
    const aToB = arrowOf(LINE_START, LINE_END, "a_to_b");
    const bToA = arrowOf(LINE_START, LINE_END, "b_to_a");

    expect(bToA.from[0]).toBeCloseTo(aToB.to[0], 9);
    expect(bToA.from[1]).toBeCloseTo(aToB.to[1], 9);
    expect(bToA.to[0]).toBeCloseTo(aToB.from[0], 9);
    expect(bToA.to[1]).toBeCloseTo(aToB.from[1], 9);
  });

  it("en una línea diagonal respeta la convención de lados", () => {
    const start: Point = [100, 200];
    const end: Point = [400, 600];

    const arrow = arrowOf(start, end, "a_to_b");

    expect(cross(start, end, arrow.from)).toBeGreaterThan(0);
    expect(cross(start, end, arrow.to)).toBeLessThan(0);
    expectOnNormalThroughMidpoint(start, end, arrow);
  });
});

describe("línea de largo 0", () => {
  it("no tiene etiquetas A/B", () => {
    expect(lineSideLabelPositions([500, 850], [500, 850])).toBeNull();
  });

  it("no tiene flecha de entrada", () => {
    expect(entryArrow([500, 850], [500, 850], "a_to_b")).toBeNull();
  });
});
