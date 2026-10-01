import { useEffect, useState } from "react";

import { API_BASE_URL } from "../api/config";
import { ApiRequestError } from "../api/http";
import { listSessions } from "../api/sessions";
import { AppShell } from "../components/AppShell";
import { Link } from "../components/Link";
import { VideoUploadForm } from "../components/VideoUploadForm";
import { navigate } from "../navigation";
import ruled from "../styles/ruled.module.css";
import type { SessionSummary, SourceKind } from "../types/session";
import { ProcessedSessionsSection } from "./ProcessedSessionsSection";

import styles from "./SessionsPage.module.css";

const SOURCE_KIND_LABEL: Record<SourceKind, string> = {
  synthetic: "Sintética",
  video_file: "Video",
};

function registeredLabel(count: number): string {
  return count === 1 ? "1 registrada" : `${count} registradas`;
}

interface SessionsPageProps {
  apiBaseUrl?: string;
}

export function SessionsPage({ apiBaseUrl = API_BASE_URL }: SessionsPageProps) {
  const [sessions, setSessions] = useState<SessionSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    listSessions(apiBaseUrl)
      .then((result) => {
        if (active) setSessions(result);
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(
            reason instanceof ApiRequestError ? reason.error.message : "Ocurrió un error inesperado.",
          );
        }
      });
    return () => {
      active = false;
    };
  }, [apiBaseUrl]);

  return (
    <AppShell title="Sesiones" context={sessions === null ? undefined : registeredLabel(sessions.length)}>
      <div className={styles.upload}>
        <VideoUploadForm
          apiBaseUrl={apiBaseUrl}
          onRegistered={(session) => navigate(`/sessions/${encodeURIComponent(session.id)}`)}
        />
      </div>

      <section aria-labelledby="sessions-title">
        <h2 id="sessions-title">Sesiones registradas</h2>
        {error !== null && <p role="alert">{error}</p>}
        {error === null && sessions === null && <p role="status">Cargando sesiones…</p>}
        {sessions !== null && sessions.length === 0 && <p>Todavía no hay sesiones registradas.</p>}
        {sessions !== null && sessions.length > 0 && (
          <table className={ruled.table}>
            <thead>
              <tr>
                <th scope="col">Nombre</th>
                <th scope="col">Cámara</th>
                <th scope="col">Tipo</th>
                <th scope="col">Creada</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((session) => (
                <tr key={session.id}>
                  <td>
                    <Link href={`/sessions/${encodeURIComponent(session.id)}`}>{session.name}</Link>
                  </td>
                  <td>{session.camera.name}</td>
                  <td>{SOURCE_KIND_LABEL[session.source_kind]}</td>
                  <td>
                    <time dateTime={session.created_at}>
                      {new Date(session.created_at).toLocaleString()}
                    </time>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <ProcessedSessionsSection apiBaseUrl={apiBaseUrl} />
    </AppShell>
  );
}
