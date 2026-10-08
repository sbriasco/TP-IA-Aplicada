import type { ReactNode } from "react";

import styles from "./results.module.css";

export function EventsTable({ label, children }: { label: string; children: ReactNode }) {
  return <div className={styles.tableScroll}><table aria-label={label}>{children}</table></div>;
}
