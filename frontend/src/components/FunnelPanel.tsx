import type { ShopFunnel } from "../api/funnel";

import styles from "./FunnelPanel.module.css";

const STAGE_NAME: Record<string, string> = {
  observed_pass: "Paso observado",
  exposure: "Con salida observada",
  stop: "Detención frente a la vidriera",
  attention: "Atención estimada",
  linked_entry: "Ingreso vinculado",
};

interface FunnelPanelProps {
  funnel: ShopFunnel;
}

export function FunnelPanel({ funnel }: FunnelPanelProps) {
  return (
    <section className={styles.panel} aria-label="Funnel comercial">
      <h2>Funnel comercial</h2>
      <ul className={styles.stages}>
        {funnel.stages.map((stage) => (
          <li key={stage.stage}>
            <span className={styles.name}>{STAGE_NAME[stage.stage] ?? stage.stage}</span>
            <span className={styles.value}>
              {stage.availability === "available" ? stage.count : "no disponible"}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
