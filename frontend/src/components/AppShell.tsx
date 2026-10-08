import type { ReactNode } from "react";
import { UserRound } from "lucide-react";
import { Link } from "./Link";
import { ThemeToggle } from "./ThemeToggle";
import styles from "./AppShell.module.css";

interface AppShellProps {
  title: string;
  context?: string;
  sessionId?: string;
  canEdit?: boolean;
  children: ReactNode;
  subtitle?: string;
  actions?: ReactNode;
  viewport?: boolean;
  hideContext?: boolean;
  pageHeader?: ReactNode;
  mainClassName?: string;
}

export function AppShell({ title, context, sessionId, canEdit = true, children, subtitle, actions, viewport = false, hideContext = false, pageHeader, mainClassName }: AppShellProps) {
  const path = sessionId === undefined ? undefined : "/sessions/" + encodeURIComponent(sessionId);
  return (
    <div className={`${styles.app} ${viewport ? styles.viewport : ""}`}>
      <a className={styles.skip} href="#main-content">Saltar al contenido</a>
      <header className={styles.bar}>
        <Link href="/" className={styles.brand} aria-label="FlowSight · Inicio"><svg viewBox="0 0 32 32" aria-hidden="true"><rect x="5" y="8" width="22" height="16" rx="4" fill="none" stroke="currentColor" strokeWidth="2"/><path d="M10 20v-6m6 6V10m6 10v-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/></svg>FlowSight</Link>
        <nav aria-label="Principal"><Link href="/" aria-current={path === undefined ? "page" : undefined}>Mis análisis</Link></nav>
        {!hideContext && context && context !== "Editor" && context !== "Detalle" && <p className={styles.context} data-context>{context}</p>}
        <div className={styles.headerControls}><ThemeToggle /><span className={styles.avatar} role="img" aria-label="Perfil local"><UserRound size={17} aria-hidden="true" /></span></div>
      </header>
      <main className={`${styles.main} ${mainClassName ?? ""}`} id="main-content" tabIndex={-1}>
        {pageHeader ?? <div className={styles.pageHeading}><div><h1>{title}</h1>{subtitle && <p className={styles.subtitle}>{subtitle}</p>}</div>{actions}
          {path && <nav className={styles.sessionNav} aria-label="Sesión">
            <Link href={path} aria-current={context === "Detalle" ? "page" : undefined}><span>1</span>Preparar análisis</Link>
            {canEdit && <Link href={path + "/editor"} aria-current={context === "Editor" ? "page" : undefined}><span>2</span>Editor de escena</Link>}
            <Link href={path + "/results"} aria-current={context === "Resultados" ? "page" : undefined}><span>3</span>Resultados</Link>
          </nav>}
        </div>}
        {children}
      </main>
    </div>
  );
}
