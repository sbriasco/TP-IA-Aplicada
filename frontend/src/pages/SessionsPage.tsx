import { useEffect, useState } from "react";

import { API_BASE_URL } from "../api/config";
import { ApiRequestError } from "../api/http";
import { listSessions } from "../api/sessions";
import { Link } from "../components/Link";
import { VideoUploadForm } from "../components/VideoUploadForm";
import { navigate } from "../navigation";
import type { SessionSummary, SourceKind } from "../types/session";

const SOURCE_KIND_LABEL: Record<SourceKind, string> = {
  synthetic: "Sintética",
  video_file: "Video",
};

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
    <main>
      <h1>Sesiones</h1>

      <VideoUploadForm
        apiBaseUrl={apiBaseUrl}
        onRegistered={(session) => navigate(`/sessions/${encodeURIComponent(session.id)}`)}
      />

      <section aria-labelledby="sessions-title">
        <h2 id="sessions-title">Sesiones registradas</h2>
        {error !== null && <p role="alert">{error}</p>}
        {error === null && sessions === null && <p role="status">Cargando sesiones…</p>}
        {sessions !== null && sessions.length === 0 && <p>Todavía no hay sesiones registradas.</p>}
        {sessions !== null && sessions.length > 0 && (
          <table>
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
    </main>
  );
}
