import { useEffect, useId, useState } from "react";

import { getSceneVersion } from "../api/scenes";
import { entryArrow } from "../editor/coordinates";
import { ENTRY_LINE_COLOR, ZONE_COLORS } from "../editor/colors";
import { ZONE_ROLE_OPTION } from "../editor/labels";
import type { Point, SceneVersion, ZoneRole } from "../types/scene";
import styles from "./ScenePreview.module.css";

const ROLES: ZoneRole[] = ["front", "interior", "showcase"];

interface ScenePreviewProps {
  apiBaseUrl: string;
  versionId: string;
  frameUrl: string;
  width: number;
  height: number;
  label: string;
  showConfigurationBadge?: boolean;
}

export function ScenePreview({ apiBaseUrl, versionId, frameUrl, width, height, label, showConfigurationBadge = true }: ScenePreviewProps) {
  const [loaded, setLoaded] = useState<{ id: string; baseUrl: string; version: SceneVersion | null; failed: boolean } | null>(null);
  const markerId = `preview-entry-${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;
  useEffect(() => {
    let active = true;
    if (versionId !== "") {
      getSceneVersion(apiBaseUrl, versionId).then((version) => {
        if (active) setLoaded({ id: versionId, baseUrl: apiBaseUrl, version, failed: false });
      }).catch(() => {
        if (active) setLoaded({ id: versionId, baseUrl: apiBaseUrl, version: null, failed: true });
      });
    }
    return () => { active = false; };
  }, [apiBaseUrl, versionId]);

  const current = loaded?.id === versionId && loaded.baseUrl === apiBaseUrl ? loaded : null;
  const version = versionId === "" ? null : current?.version ?? null;
  const compatible = version !== null && Math.abs((width / height) / (version.frame_width / version.frame_height) - 1) <= 0.01;
  const unit = Math.max(width, height) / 100;
  const pixels = ([x, y]: Point): Point => [x * width, y * height];
  const status = versionId === "" ? null : current === null ? "Cargando zonas…" : current.failed
    ? "No se pudieron cargar las zonas. Volvé a seleccionar la configuración."
    : !compatible ? "Esta configuración tiene otro formato de imagen. Creá una para este video."
    : `Configuración ${version?.version_number}`;

  return <div className={styles.preview}>
    <svg className={styles.canvas} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="xMidYMid meet" role="img" aria-label={label}>
      <defs><marker id={markerId} markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0 0L7 3.5L0 7Z" fill={ENTRY_LINE_COLOR} /></marker></defs>
      <image href={frameUrl} width={width} height={height} />
      {compatible && version?.shops.map((shop) => <g key={shop.shop_id}>
        {ROLES.map((role) => {
          const points = shop.zones[role];
          if (points == null || points.length === 0) return null;
          const center = points.reduce<Point>((sum, point) => [sum[0] + point[0] * width / points.length, sum[1] + point[1] * height / points.length], [0, 0]);
          return <g key={role}>
            <polygon points={points.map((point) => pixels(point).join(",")).join(" ")} fill={ZONE_COLORS[role]} fillOpacity="0.12" stroke={ZONE_COLORS[role]} strokeWidth={unit * 0.4} strokeDasharray={role === "front" ? undefined : role === "interior" ? `${unit * 1.4} ${unit * 0.7}` : `${unit * 0.3} ${unit * 0.6}`}><title>{ZONE_ROLE_OPTION[role]} · {shop.name}</title></polygon>
            <text x={center[0]} y={center[1]} textAnchor="middle" className={styles.zoneLabel} fontSize={unit * 1.8} strokeWidth={unit * 0.5}>{ZONE_ROLE_OPTION[role]} · {shop.name}</text>
          </g>;
        })}
        {(() => {
          const start = pixels(shop.entry_line.start);
          const end = pixels(shop.entry_line.end);
          const arrow = entryArrow(start, end, shop.entry_line.entry_direction);
          return <g stroke={ENTRY_LINE_COLOR} strokeWidth={unit * 0.6}>
            <title>Línea de entrada · {shop.name}</title>
            <line x1={start[0]} y1={start[1]} x2={end[0]} y2={end[1]} />
            {arrow !== null && <line x1={arrow.from[0]} y1={arrow.from[1]} x2={arrow.to[0]} y2={arrow.to[1]} markerEnd={`url(#${markerId})`} />}
          </g>;
        })()}
      </g>)}
    </svg>
    {status !== null && (showConfigurationBadge || !compatible) && <span className={styles.status} role={current?.failed ? "alert" : "status"}>{status}</span>}
  </div>;
}
