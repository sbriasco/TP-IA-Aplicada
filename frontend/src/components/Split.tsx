import type { ReactNode } from "react";

import styles from "./Split.module.css";

interface SplitProps {
  main?: ReactNode;
  side: ReactNode;
  editor?: boolean;
}

export function Split({ main, side, editor = false }: SplitProps) {
  if (main === undefined || main === null) {
    return <div className={styles.side}>{side}</div>;
  }

  return (
    <div className={editor ? `${styles.split} ${styles.editor}` : styles.split}>
      <div className={styles.frame}>{main}</div>
      <div className={styles.side}>{side}</div>
    </div>
  );
}
