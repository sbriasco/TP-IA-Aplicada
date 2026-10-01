import type { ReactNode } from "react";

import styles from "./Split.module.css";

interface SplitProps {
  main?: ReactNode;
  side: ReactNode;
}

export function Split({ main, side }: SplitProps) {
  if (main === undefined || main === null) {
    return <div className={styles.side}>{side}</div>;
  }

  return (
    <div className={styles.split}>
      <div className={styles.frame}>{main}</div>
      <div className={styles.side}>{side}</div>
    </div>
  );
}
