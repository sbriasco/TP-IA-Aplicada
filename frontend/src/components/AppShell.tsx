import type { ReactNode } from "react";
import { Link } from "./Link";
import styles from "./AppShell.module.css";

interface AppShellProps {
  title: string;
  context?: string;
  sessionId?: string;
  canEdit?: boolean;
  children: ReactNode;
}

export function AppShell({ title, context, sessionId, canEdit = true, children }: AppShellProps) {
  const path = sessionId === undefined ? undefined : "/sessions/" + encodeURIComponent(sessionId);
  return (
    <div className={styles.app}>
      <a className={styles.skip} href="#main-content">Saltar al contenido</a>
      <header className={styles.bar}>
        <Link href="/" className={styles.brand} aria-label="FlowSight · Inicio"><svg viewBox="0 0 32 32" aria-hidden="true"><rect x="5" y="8" width="22" height="16" rx="4" fill="none" stroke="currentColor" strokeWidth="2"/><path d="M10 20v-6m6 6V10m6 10v-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/></svg>FlowSight</Link>
        <nav aria-label="Principal"><Link href="/" aria-current={path === undefined ? "page" : undefined}>Mis análisis</Link></nav>
        {context && <p className={styles.context} data-context>{context === "Detalle" ? "Preparar análisis" : context}</p>}
      </header>
      <main className={styles.main} id="main-content" tabIndex={-1}>
        <div className={styles.pageHeading}><h1>{title}</h1>
          {path && <nav className={styles.sessionNav} aria-label="Sesión">
            <Link href={path} aria-current={context === "Detalle" ? "page" : undefined}><span>1</span>Preparar análisis</Link>
            {canEdit && <Link href={path + "/editor"} aria-current={context === "Editor" ? "page" : undefined}><span>2</span>Editor de escena</Link>}
            <Link href={path + "/results"} aria-current={context === "Resultados" ? "page" : undefined}><span>3</span>Resultados</Link>
          </nav>}
        </div>
        {children}
      </main>
    </div>
  );
}
