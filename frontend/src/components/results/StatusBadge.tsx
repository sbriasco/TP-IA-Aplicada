import { Ban, CheckCircle2, CircleDot, XCircle } from "lucide-react";

import styles from "./results.module.css";

export function StatusBadge({ source, status }: { source: "video" | "webcam"; status: string }) {
  const live = source === "webcam";
  if (status === "completed") {
    return <span className={styles.success}><CheckCircle2 size={14} aria-hidden="true" />{live ? "Captura finalizada" : "Análisis finalizado"}</span>;
  }
  if (status === "cancelled") {
    return <span className={styles.cancelled}><Ban size={14} aria-hidden="true" />{live ? "Captura cancelada" : "Análisis cancelado"}</span>;
  }
  if (status === "failed") {
    return <span className={styles.failed}><XCircle size={14} aria-hidden="true" />{live ? "Captura fallida" : "Análisis fallido"}</span>;
  }
  return <span className={styles.neutral}><CircleDot size={14} aria-hidden="true" />{live ? "Captura en curso" : "Análisis en curso"}</span>;
}
