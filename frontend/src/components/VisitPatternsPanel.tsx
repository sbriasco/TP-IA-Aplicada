import { useState } from "react";

import type { VisitPatterns } from "../api/visitPatterns";
import { sequenceLabel, type SequenceZone } from "../presentation/sequenceLabel";

import styles from "./VisitPatternsPanel.module.css";

interface VisitPatternsPanelProps {
  patterns: VisitPatterns;
  zones?: SequenceZone[];
}

function groupSummary(count: number): string {
  if (count === 1) return "1 grupo estimado";
  return `${count} grupos estimados`;
}

export function VisitPatternsPanel({ patterns, zones = [] }: VisitPatternsPanelProps) {
  const [open, setOpen] = useState(false);
  const groupsReady = patterns.groups_availability === "available";
  const ranked = patterns.sequences
    .map((sequence, index) => ({ sequence, index }))
    .sort((left, right) => right.sequence.track_count - left.sequence.track_count || left.index - right.index);
  const visible = open ? ranked : ranked.slice(0, 5);

  return (
    <section className={styles.panel} aria-label="Patrones de visita">
      <h2>Patrones de visita</h2>
      {ranked.length === 0 ? (
        <p className={styles.note}>No hay secuencias.</p>
      ) : (
        <>
          <ul className={styles.list}>
            {visible.map((item) => (
              <li key={item.index}>
                <span className={styles.name}>{sequenceLabel(item.sequence.areas, zones)}</span>
                <span className={styles.value}>{item.sequence.track_count}</span>
              </li>
            ))}
          </ul>
          {ranked.length > 5 && (
            <button type="button" aria-expanded={open} onClick={() => setOpen((current) => !current)}>
              {open ? "Ocultar el resto de las secuencias" : "Ver el resto de las secuencias"}
            </button>
          )}
        </>
      )}
      <h2>Grupos estimados</h2>
      <p className={styles.value}>{groupsReady ? groupSummary(patterns.group_count) : "no disponible"}</p>
    </section>
  );
}
