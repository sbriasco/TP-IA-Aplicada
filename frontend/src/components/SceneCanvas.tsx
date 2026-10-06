import {
  useId,
  useRef,
  type Dispatch,
  type KeyboardEvent,
  type MouseEvent,
  type PointerEvent,
} from "react";

import { entryArrow, lineSideLabelPositions, screenToFrame } from "../editor/coordinates";
import {
  hasIssue,
  issuesFor,
  type EditorAction,
  type EditorElement,
  type EditorSelection,
  type EditorState,
  type NudgeDirection,
} from "../editor/editorState";
import { elementName, elementTitle, shopDisplayName, ZONE_ROLE_OPTION } from "../editor/labels";
import type { Point, ZoneRole } from "../types/scene";

interface SceneCanvasProps {
  state: EditorState;
  dispatch: Dispatch<EditorAction>;
  /** URL absoluta del frame de referencia de la sesión. */
  frameUrl: string;
  hidden?: ReadonlySet<string>;
  onGestureStart?: () => void;
  onGestureEnd?: () => void;
}

/**
 * Lienzo SVG del editor (T042). El `viewBox` está en píxeles del frame y `xMidYMid meet` mantiene
 * la correspondencia al redimensionar (FR-033). No guarda geometría: todo va por `dispatch`.
 */

// Además del color, cada rol tiene su propio trazo (sólido, rayado, punteado) y su nombre escrito.
const ROLE_STYLE: Record<ZoneRole, { color: string; dash: (unit: number) => string | undefined }> = {
  front: { color: "#1565c0", dash: () => undefined },
  interior: { color: "#2e7d32", dash: (unit) => `${unit * 1.4} ${unit * 0.7}` },
  showcase: { color: "#16a34a", dash: (unit) => `${unit * 0.3} ${unit * 0.6}` },
};
const LINE_COLOR = "#6a1b9a";
const ERROR_COLOR = "#c62828";
const HALO = "#ffffff";
/** Largo máximo del mensaje de error visible dentro del frame; el completo va en `<title>`. */
const ISSUE_TEXT_MAX = 48;

const ARROW_KEYS: Record<string, NudgeDirection> = {
  ArrowUp: "up",
  ArrowDown: "down",
  ArrowLeft: "left",
  ArrowRight: "right",
};

interface VertexRef {
  shopIndex: number;
  element: EditorElement;
  vertexIndex: number;
}

function pointsAttr(points: Point[]): string {
  return points.map(([x, y]) => `${x},${y}`).join(" ");
}

function centroid(points: Point[]): Point {
  const sum = points.reduce<Point>((acc, [x, y]) => [acc[0] + x, acc[1] + y], [0, 0]);
  return [sum[0] / points.length, sum[1] / points.length];
}

function sameVertex(a: EditorSelection | VertexRef | null, b: VertexRef): boolean {
  return (
    a !== null &&
    a.shopIndex === b.shopIndex &&
    a.element === b.element &&
    a.vertexIndex === b.vertexIndex
  );
}

export function SceneCanvas({ state, dispatch, frameUrl, hidden, onGestureStart, onGestureEnd }: SceneCanvasProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const dragRef = useRef<VertexRef | null>(null);
  const markerId = `entry-arrow-${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;

  const { frameWidth: width, frameHeight: height, selection, drawing } = state;
  // Unidad visual proporcional al frame, para que vértices y textos no dependan de la resolución.
  const unit = Math.max(width, height) / 100;
  const fontSize = unit * 1.8;
  const radius = unit * 0.8;

  function toFrame(clientX: number, clientY: number): Point | null {
    return svgRef.current === null ? null : screenToFrame(svgRef.current, clientX, clientY);
  }

  function isSelected(shopIndex: number, element: EditorElement): boolean {
    return selection !== null && selection.shopIndex === shopIndex && selection.element === element;
  }

  /**
   * La flecha (`entryArrow`, centrada en el punto medio) cruzaría las etiquetas A/B, que están a
   * ±20 px sobre la misma normal: se corre a lo largo de la línea para que no se tapen.
   */
  function arrowShift(start: Point, end: Point): string | undefined {
    const length = Math.hypot(end[0] - start[0], end[1] - start[1]);
    if (length === 0) return undefined;
    const shift = Math.min(fontSize * 1.6, length / 2);
    return `translate(${((end[0] - start[0]) / length) * shift} ${((end[1] - start[1]) / length) * shift})`;
  }

  function handleBackgroundClick(event: MouseEvent<SVGSVGElement>) {
    if (drawing === null || event.detail > 1) return;
    const point = toFrame(event.clientX, event.clientY);
    if (point !== null) dispatch({ type: "addPoint", point });
  }

  function handleCanvasKeyDown(event: KeyboardEvent<SVGSVGElement>) {
    if (drawing === null) return;
    if (event.key === "Enter") {
      event.preventDefault();
      dispatch({ type: "finishDrawing" });
    } else if (event.key === "Escape") {
      event.preventDefault();
      dispatch({ type: "cancelDrawing" });
    }
  }

  function vertexHandlers(vertex: VertexRef) {
    const select = () => dispatch({ type: "select", selection: vertex });
    return {
      onFocus: () => {
        if (!sameVertex(selection, vertex)) select();
      },
      onClick: (event: MouseEvent<SVGCircleElement>) => {
        // No es un clic sobre el fondo: no agrega un vértice al dibujo en curso.
        event.stopPropagation();
      },
      onKeyDown: (event: KeyboardEvent<SVGCircleElement>) => {
        const direction = ARROW_KEYS[event.key];
        if (direction !== undefined) {
          event.preventDefault();
          dispatch({ type: "nudgeVertex", ...vertex, direction, large: event.shiftKey });
        } else if (event.key === "Delete" || event.key === "Backspace") {
          event.preventDefault();
          dispatch({ type: "deleteVertex", ...vertex });
        }
      },
      onPointerDown: (event: PointerEvent<SVGCircleElement>) => {
        if (event.button !== 0) return;
        onGestureStart?.();
        event.stopPropagation();
        const target = event.currentTarget;
        if (typeof target.setPointerCapture === "function" && event.pointerId !== undefined) {
          target.setPointerCapture(event.pointerId);
        }
        dragRef.current = vertex;
        if (!sameVertex(selection, vertex)) select();
      },
      onPointerMove: (event: PointerEvent<SVGCircleElement>) => {
        if (!sameVertex(dragRef.current, vertex)) return;
        const point = toFrame(event.clientX, event.clientY);
        if (point !== null) dispatch({ type: "moveVertex", ...vertex, point });
      },
      onPointerUp: (event: PointerEvent<SVGCircleElement>) => {
        const target = event.currentTarget;
        if (typeof target.hasPointerCapture === "function" && target.hasPointerCapture(event.pointerId)) {
          target.releasePointerCapture(event.pointerId);
        }
        dragRef.current = null;
        onGestureEnd?.();
      },
      onPointerCancel: () => {
        dragRef.current = null;
        onGestureEnd?.();
      },
    };
  }

  /**
   * Error sobre el elemento (FR-034): `<title>` con todos los mensajes (tooltip y descripción) y un
   * texto corto visible, anclado hacia adentro del frame para no salirse por el borde.
   */
  function issueText(shopIndex: number, element: EditorElement, anchor: Point) {
    const messages = issuesFor(state, shopIndex, element).map((item) => item.message);
    if (messages.length === 0) return null;
    const first = messages[0];
    const short = first.length > ISSUE_TEXT_MAX ? `${first.slice(0, ISSUE_TEXT_MAX - 1)}…` : first;
    const more = messages.length > 1 ? ` (+${messages.length - 1})` : "";
    const rightHalf = anchor[0] > width / 2;
    return (
      <text
        x={anchor[0]}
        y={Math.max(anchor[1] - unit * 1.5, fontSize)}
        textAnchor={rightHalf ? "end" : "start"}
        fontSize={fontSize}
        fill={ERROR_COLOR}
        stroke={HALO}
        strokeWidth={unit * 0.3}
        paintOrder="stroke"
        fontWeight="bold"
        aria-hidden="true"
      >
        ⚠ {short}
        {more}
      </text>
    );
  }

  /** Todos los mensajes como `<title>`: primer hijo del grupo, para que sea su descripción. */
  function issueTitle(shopIndex: number, element: EditorElement) {
    const messages = issuesFor(state, shopIndex, element).map((item) => item.message);
    return messages.length === 0 ? null : <title>{messages.join("\n")}</title>;
  }

  const shapes = state.shops.flatMap((shop, shopIndex) => {
    const shopName = shopDisplayName(shop.name, shopIndex);
    const nodes = (Object.keys(ROLE_STYLE) as ZoneRole[]).flatMap((role) => {
      const points = shop.zones[role];
      if (points === undefined) return [];
      const element: EditorElement = `zone:${role}`;
      if (hidden?.has(`${shop.key}/${element}`)) return [];
      const invalid = hasIssue(state, shopIndex, element);
      const selected = isSelected(shopIndex, element);
      const style = ROLE_STYLE[role];
      const center = centroid(points);
      return [
        <g
          key={`${shop.key}-${element}`}
          role="group"
          aria-label={`${elementTitle(element)} de ${shopName}`}
          aria-invalid={invalid ? true : undefined}
          onClick={event => { if (drawing === null) { event.stopPropagation(); dispatch({ type: "select", selection: { shopIndex, element, vertexIndex: null } }); } }}
        >
          {issueTitle(shopIndex, element)}
          <polygon
            points={pointsAttr(points)}
            data-role={role}
            fill={style.color}
            fillOpacity={selected ? 0.3 : 0.15}
            stroke={invalid ? ERROR_COLOR : style.color}
            strokeWidth={unit * (invalid ? 0.6 : selected ? 0.45 : 0.3)}
            strokeDasharray={style.dash(unit)}
            strokeLinejoin="round"
          />
          <text
            x={center[0]}
            y={center[1]}
            textAnchor="middle"
            dominantBaseline="middle"
            fontSize={fontSize}
            fill={style.color}
            stroke={HALO}
            strokeWidth={unit * 0.3}
            paintOrder="stroke"
            aria-hidden="true"
          >
            {ZONE_ROLE_OPTION[role]} · {shopName}
          </text>
          {issueText(shopIndex, element, points[0])}
        </g>,
      ];
    });

    const line = shop.entry_line;
    if (line !== null && !hidden?.has(`${shop.key}/entry_line`)) {
      const invalid = hasIssue(state, shopIndex, "entry_line");
      const selected = isSelected(shopIndex, "entry_line");
      const labels = lineSideLabelPositions(line.start, line.end);
      const arrow = entryArrow(line.start, line.end, line.entry_direction);
      const labelProps = {
        role: "img",
        textAnchor: "middle",
        dominantBaseline: "middle",
        fontSize: fontSize * 1.2,
        fontWeight: "bold",
        fill: LINE_COLOR,
        stroke: HALO,
        strokeWidth: unit * 0.3,
        paintOrder: "stroke",
      } as const;
      nodes.push(
        <g
          key={`${shop.key}-entry_line`}
          role="group"
          aria-label={`Línea de entrada de ${shopName}`}
          onClick={event => { if (drawing === null) { event.stopPropagation(); dispatch({ type: "select", selection: { shopIndex, element: "entry_line", vertexIndex: null } }); } }}
          aria-invalid={invalid ? true : undefined}
        >
          {issueTitle(shopIndex, "entry_line")}
          <line
            x1={line.start[0]}
            y1={line.start[1]}
            x2={line.end[0]}
            y2={line.end[1]}
            stroke={HALO}
            strokeWidth={unit * 0.9}
            strokeLinecap="round"
            aria-hidden="true"
          />
          <line
            x1={line.start[0]}
            y1={line.start[1]}
            x2={line.end[0]}
            y2={line.end[1]}
            stroke={invalid ? ERROR_COLOR : LINE_COLOR}
            strokeWidth={unit * (invalid ? 0.7 : selected ? 0.55 : 0.4)}
            strokeLinecap="round"
          />
          {labels !== null && (
            <>
              <text {...labelProps} x={labels.A[0]} y={labels.A[1]} aria-label={`Lado A de ${shopName}`}>
                A
              </text>
              <text {...labelProps} x={labels.B[0]} y={labels.B[1]} aria-label={`Lado B de ${shopName}`}>
                B
              </text>
            </>
          )}
          {arrow !== null && (
            <g
              role="img"
              aria-label={`Flecha de entrada de ${shopName}: ${
                line.entry_direction === "a_to_b" ? "de A a B" : "de B a A"
              }`}
              transform={arrowShift(line.start, line.end)}
            >
              <line
                x1={arrow.from[0]}
                y1={arrow.from[1]}
                x2={arrow.to[0]}
                y2={arrow.to[1]}
                stroke={HALO}
                strokeWidth={unit * 0.8}
                strokeLinecap="round"
              />
              <line
                x1={arrow.from[0]}
                y1={arrow.from[1]}
                x2={arrow.to[0]}
                y2={arrow.to[1]}
                stroke={LINE_COLOR}
                strokeWidth={unit * 0.35}
                markerEnd={`url(#${markerId})`}
              />
            </g>
          )}
          {issueText(shopIndex, "entry_line", line.start)}
        </g>,
      );
    }
    return nodes;
  });

  const vertices = state.shops.flatMap((shop, shopIndex) => {
    const shopName = shopDisplayName(shop.name, shopIndex);
    const elements: [EditorElement, Point[], string][] = [];
    for (const role of Object.keys(ROLE_STYLE) as ZoneRole[]) {
      const points = shop.zones[role];
      if (points !== undefined) elements.push([`zone:${role}`, points, ROLE_STYLE[role].color]);
    }
    if (shop.entry_line !== null) {
      elements.push(["entry_line", [shop.entry_line.start, shop.entry_line.end], LINE_COLOR]);
    }
    return elements.filter(([element]) => !hidden?.has(`${shop.key}/${element}`)).flatMap(([element, points, color]) =>
      points.map((point, vertexIndex) => {
        const vertex: VertexRef = { shopIndex, element, vertexIndex };
        const selected = sameVertex(selection, vertex);
        return (
          <circle
            key={`${shop.key}-${element}-${vertexIndex}`}
            role="button"
            tabIndex={0}
            aria-label={`Vértice ${vertexIndex + 1} de ${elementName(element)} de ${shopName}`}
            aria-pressed={selected}
            cx={point[0]}
            cy={point[1]}
            r={selected ? radius * 1.4 : radius}
            fill={selected ? color : HALO}
            stroke={color}
            strokeWidth={unit * 0.3}
            style={{ cursor: "move" }}
            {...vertexHandlers(vertex)}
          />
        );
      }),
    );
  });

  let preview = null;
  if (drawing !== null && drawing.points.length > 0) {
    const color =
      drawing.element === "entry_line"
        ? LINE_COLOR
        : ROLE_STYLE[drawing.element.slice("zone:".length) as ZoneRole].color;
    preview = (
      <g data-drawing="true" aria-hidden="true" pointerEvents="none">
        <polyline
          points={pointsAttr(
            drawing.element !== "entry_line" && drawing.points.length >= 3
              ? [...drawing.points, drawing.points[0]]
              : drawing.points,
          )}
          fill="none"
          stroke={color}
          strokeWidth={unit * 0.3}
          strokeDasharray={`${unit} ${unit * 0.5}`}
        />
        {drawing.points.map((point, index) => (
          <circle key={index} cx={point[0]} cy={point[1]} r={radius * 0.8} fill={color} />
        ))}
      </g>
    );
  }

  return (
    <svg
      ref={svgRef}
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="xMidYMid meet"
      role="group"
      aria-label="Frame de referencia con la escena"
      tabIndex={drawing !== null ? 0 : undefined}
      onClick={handleBackgroundClick}
      onDoubleClick={() => { if (drawing !== null && drawing.element !== "entry_line" && drawing.points.length >= 3) dispatch({ type: "finishDrawing" }); }}
      onKeyDown={handleCanvasKeyDown}
      style={{
        display: "block",
        width: "100%",
        height: "var(--scene-canvas-height, auto)",
        maxHeight: "var(--scene-canvas-max-height, max(240px, calc(100dvh - 250px)))",
        background: "#1f1f1f",
        cursor: drawing !== null ? "crosshair" : "default",
        touchAction: "none",
      }}
    >
      <defs>
        <marker
          id={markerId}
          viewBox="0 0 10 10"
          refX="5"
          refY="5"
          markerWidth="3.5"
          markerHeight="3.5"
          orient="auto-start-reverse"
          overflow="visible"
        >
          <path d="M0,0 L10,5 L0,10 z" fill={LINE_COLOR} stroke={HALO} strokeWidth="1.5" />
        </marker>
      </defs>
      <image href={frameUrl} x={0} y={0} width={width} height={height} />
      {shapes}
      {preview}
      {vertices}
    </svg>
  );
}
