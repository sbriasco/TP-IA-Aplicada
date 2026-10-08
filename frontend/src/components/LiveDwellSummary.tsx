import type { LiveZoneDwell } from "../api/liveMessages";
import styles from "./LiveDwellSummary.module.css";

export function LiveDwellSummary({ dwell, compact = false }: { dwell?: LiveZoneDwell; compact?: boolean }) {
  function format(value: number | null | undefined): string {
    if (value === undefined || value === null || value <= 0) return compact ? "--" : "Sin datos";
    return value < .1 ? "< 0,1 s" : `${value.toLocaleString("es-AR", { maximumFractionDigits: 1 })} s`;
  }
  return <section aria-label="Estadía promedio por zona">
    <h2>{compact ? "Tiempo promedio de estadía" : "Estadía promedio"}</h2>
    <dl className={styles.metrics}>
      <div><dt>Zona interna</dt><dd aria-label="Estadía promedio interna">{format(dwell?.interior_average_seconds)}</dd></div>
      <div><dt>Zona externa</dt><dd aria-label="Estadía promedio externa">{format(dwell?.front_average_seconds)}</dd></div>
    </dl>
    {compact ? <details><summary>Cómo se calcula la estadía</summary><p className={styles.note}>Tiempo observado por visita, incluidas las visitas en curso. Se excluyen duraciones de cero y períodos sin seguimiento.</p></details> : <p className={styles.note}>Tiempo observado por visita, incluidas las visitas en curso. Se excluyen duraciones de cero y períodos sin seguimiento.</p>}
  </section>;
}
