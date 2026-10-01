import type { ReactNode } from "react";

import styles from "./AppShell.module.css";

interface AppShellProps {
  title: string;
  context?: string;
  children: ReactNode;
}

export function AppShell({ title, context, children }: AppShellProps) {
  return (
    <div>
      <header className={styles.bar}>
        <h1>{title}</h1>
        {context !== undefined && context !== "" && <p className={styles.context}>{context}</p>}
      </header>
      <main className={styles.main}>{children}</main>
    </div>
  );
}
