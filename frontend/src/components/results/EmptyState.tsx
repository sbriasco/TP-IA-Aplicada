import type { ReactNode } from "react";

import styles from "./results.module.css";

export function EmptyState({ title, children, icon }: { title: string; children: ReactNode; icon?: ReactNode }) {
  return <div className={styles.empty}>
    {icon}
    <h3>{title}</h3>
    <p>{children}</p>
  </div>;
}
