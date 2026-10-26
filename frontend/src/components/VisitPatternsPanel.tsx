import type { AreaRef, VisitPatterns } from "../api/visitPatterns";

import styles from "./VisitPatternsPanel.module.css";

const ROLE_NAME: Record<AreaRef["zone_role"], string> = {
  front: "frente",
  interior: "interior",
  window: "vidriera",
};

interface NamedShop {
  shop_id: string;
  name: string;
}

interface VisitPatternsPanelProps {
  patterns: VisitPatterns;
  shops: NamedShop[];
}

function shopName(shops: NamedShop[], shopId: string): string {
  return shops.find((shop) => shop.shop_id === shopId)?.name ?? shopId;
}

function areaName(shops: NamedShop[], shopId: string, role: AreaRef["zone_role"]): string {
  return `${shopName(shops, shopId)} · ${ROLE_NAME[role]}`;
}

export function VisitPatternsPanel({ patterns, shops }: VisitPatternsPanelProps) {
  const patternsReady = patterns.patterns_availability === "available";
  const noAreas = patterns.patterns_unavailable_reason === "no_areas";
  const groupsReady = patterns.groups_availability === "available";

  return (
    <section className={styles.panel} aria-label="Patrones de visita y grupos estimados">
      <h2>Patrones de visita y grupos estimados</h2>
      {noAreas && <p className={styles.note}>No hay áreas.</p>}
      {patternsReady && (
        <>
          <h3>Transiciones entre áreas</h3>
          <ul className={styles.list}>
            {patterns.area_transitions.map((step) => (
              <li key={`${step.from_shop_id}-${step.from_zone_role}-${step.to_shop_id}-${step.to_zone_role}`}>
                <span className={styles.name}>
                  De {areaName(shops, step.from_shop_id, step.from_zone_role)} a{" "}
                  {areaName(shops, step.to_shop_id, step.to_zone_role)}
                </span>
                <span className={styles.value}>{step.track_count}</span>
              </li>
            ))}
          </ul>
          <h3>Secuencias</h3>
          <ul className={styles.list}>
            {patterns.sequences.map((sequence) => (
              <li key={sequence.areas.map((area) => `${area.shop_id}:${area.zone_role}`).join(">")}>
                <span className={styles.name}>
                  {sequence.areas.map((area) => areaName(shops, area.shop_id, area.zone_role)).join(" → ")}
                </span>
                <span className={styles.value}>{sequence.track_count}</span>
              </li>
            ))}
          </ul>
          <h3>Cambios de local</h3>
          <ul className={styles.list}>
            {patterns.shop_transitions.map((step) => (
              <li key={`${step.from_shop_id}-${step.to_shop_id}`}>
                <span className={styles.name}>
                  De {shopName(shops, step.from_shop_id)} a {shopName(shops, step.to_shop_id)}
                </span>
                <span className={styles.value}>{step.track_count}</span>
              </li>
            ))}
          </ul>
        </>
      )}
      <h3>Grupos estimados</h3>
      {groupsReady && patterns.group_count === 0 && <p className={styles.note}>0 grupos estimados</p>}
      <ul className={styles.list}>
        {patterns.groups.map((group) => (
          <li key={group.ordinal}>
            <span className={styles.name}>{group.track_ids.map((trackId) => `Visita ${trackId}`).join(", ")}</span>
            <span className={styles.value}>
              {group.started_video_timestamp_seconds}–{group.ended_video_timestamp_seconds} s
            </span>
            <p className={styles.note}>Estimación. No afirma una relación real.</p>
          </li>
        ))}
      </ul>
      <p className={styles.note}>
        Umbrales: ocho centésimas del ancho del encuadre, 45 grados y 2 segundos de video.
      </p>
      {patterns.precision_uncommitted && (
        <p className={styles.disclaimer}>
          La precisión de los patrones y de los grupos estimados no está comprometida.
        </p>
      )}
    </section>
  );
}
