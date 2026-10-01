import { useEffect, useState } from "react";

import { ApiRequestError } from "../api/http";
import { listProcessedSessions, type ProcessedSession } from "../api/processedSessions";
import { Link } from "../components/Link";
import ruled from "../styles/ruled.module.css";

import styles from "./ProcessedSessionsSection.module.css";

const STATUS_LABEL: Record<ProcessedSession["status"], string> = {
  pending: "Pendiente",
  processing: "En curso",
  completed: "Completado",
  failed: "Fallido",
  cancelled: "Cancelado",
};

interface ProcessedSessionsSectionProps {
  apiBaseUrl: string;
}

export function ProcessedSessionsSection({ apiBaseUrl }: ProcessedSessionsSectionProps) {
  const [rows, setRows] = useState<ProcessedSession[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    listProcessedSessions(apiBaseUrl)
      .then((result) => {
        if (active) setRows(result);
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
    <section className={styles.section} aria-labelledby="processed-sessions-title">
      <h2 id="processed-sessions-title">Sesiones procesadas</h2>
      {error !== null && <p role="alert">{error}</p>}
      {error === null && rows === null && <p role="status">Cargando sesiones procesadas…</p>}
      {rows !== null && rows.length === 0 && <p>Todavía no hay sesiones procesadas.</p>}
      {rows !== null && rows.length > 0 && (
        <table className={ruled.table}>
          <thead>
            <tr>
              <th scope="col">Nombre</th>
              <th scope="col">Video</th>
              <th scope="col">Estado</th>
              <th scope="col">Fecha de procesamiento</th>
              <th scope="col">Versión</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.session_id}>
                <td>
                  <Link href={`/sessions/${encodeURIComponent(row.session_id)}/results`}>{row.name}</Link>
                </td>
                <td>{row.video_filename ?? "Sin video"}</td>
                <td>
                  {STATUS_LABEL[row.status]}
                  {(row.status === "failed" || row.status === "cancelled") && (
                    <p className={styles.reason}>{row.failure_message ?? row.failure_code}</p>
                  )}
                </td>
                <td>
                  {row.finished_at === null ? (
                    "Sin fecha"
                  ) : (
                    <time dateTime={row.finished_at}>{new Date(row.finished_at).toLocaleString()}</time>
                  )}
                </td>
                <td>{row.version_number === null ? "Sin versión" : row.version_number}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
