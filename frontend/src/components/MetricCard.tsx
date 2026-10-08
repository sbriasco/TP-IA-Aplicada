import type { MetricValue } from "../api/metrics";
import { formatMetric, LABEL_TEXT, METRIC_DESCRIPTION, METRIC_NAME, UNAVAILABLE_REASON } from "../presentation/metrics";
import styles from "./MetricCard.module.css";

export function MetricCard({ metric, prominent = false }: { metric: MetricValue; prominent?: boolean }) {
  const title = prominent && metric.code === "traffic_total" ? "Tráfico estimado" : prominent && metric.code === "entries" ? "Entradas registradas" : METRIC_NAME[metric.code] ?? metric.code;
  const available = metric.availability === "available" && metric.value !== null;
  return (
    <li className={`${styles.card}${prominent ? ` ${styles.prominent}` : ""}`}>
      <span className={styles.name}>{title}</span>
      <strong className={available ? styles.value : styles.unavailable}>
        {available ? formatMetric(metric.code, metric.value as number) : "no disponible"}
      </strong>
      <details className={styles.definition}><summary aria-label={`Cómo se mide ${METRIC_NAME[metric.code] ?? metric.code}`}>i</summary><span className={styles.description}>
        {!available && metric.unavailable_reason !== null
          ? UNAVAILABLE_REASON[metric.unavailable_reason] ?? "No hay datos suficientes"
          : METRIC_DESCRIPTION[metric.code]}
      </span></details>
      {prominent && metric.code === "dwell_mean_seconds" ? <span className={styles.estimate}>Promedio observable</span> : LABEL_TEXT[metric.label] !== undefined && <span className={styles.estimate}>{LABEL_TEXT[metric.label]}</span>}
    </li>
  );
}
