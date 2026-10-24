import type { ShopFunnel } from "../api/funnel";

import styles from "./FunnelPanel.module.css";

const STAGE_NAME: Record<string, string> = {
  observed_pass: "Paso observado",
  exposure: "Exposición a la vidriera",
  stop: "Detención frente a la vidriera",
  attention: "Atención estimada",
  linked_entry: "Ingreso vinculado",
};

const RATE_NAME: Record<string, string> = {
  observed_pass_to_exposure: "De paso observado a exposición",
  exposure_to_stop: "De exposición a detención",
  stop_to_attention: "De detención a atención estimada",
  attention_to_linked_entry: "De atención estimada a ingreso vinculado",
};

interface FunnelPanelProps {
  funnel: ShopFunnel;
  officialEntries: number | null;
}

function formatRate(value: string): string {
  const number = Number(value);
  if (!Number.isFinite(number)) return "no disponible";
  return new Intl.NumberFormat("es-AR", { style: "percent", maximumFractionDigits: 1 }).format(number);
}

export function FunnelPanel({ funnel, officialEntries }: FunnelPanelProps) {
  const thresholds: Record<string, string> = {
    stop: funnel.stop_threshold_seconds,
    attention: funnel.attention_threshold_seconds,
  };
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
            {thresholds[stage.stage] != null && (
              <p className={styles.note}>Umbral: {thresholds[stage.stage]} s de video.</p>
            )}
            {stage.label === "attention_estimate" && (
              <p className={styles.note}>Estimación. No afirma que haya mirado la vidriera.</p>
            )}
            {stage.stage === "linked_entry" && (
              <p className={styles.note}>No es el total de entradas ni una compra.</p>
            )}
            {stage.unavailable_reason === "no_showcase" && (
              <p className={styles.note}>No hay zona de vidriera.</p>
            )}
          </li>
        ))}
      </ul>
      <p className={styles.note}>
        Ingresos oficiales: {officialEntries === null ? "no disponible" : officialEntries}
      </p>
      <ul className={styles.rates}>
        {funnel.rates.map((rate) => (
          <li key={rate.code}>
            <span className={styles.name}>{RATE_NAME[rate.code] ?? rate.code}</span>
            <span className={styles.value}>
              {rate.availability === "available" && rate.value !== null
                ? formatRate(rate.value)
                : "no disponible"}
            </span>
          </li>
        ))}
      </ul>
      {funnel.excluded_window_only > 0 && (
        <p className={styles.excluded}>
          {funnel.excluded_window_only} visitas estuvieron en la vidriera y no pasaron por el frente. Quedan fuera del funnel.
        </p>
      )}
      {funnel.precision_uncommitted && (
        <p className={styles.disclaimer}>La precisión de estas etapas no está comprometida.</p>
      )}
    </section>
  );
}
