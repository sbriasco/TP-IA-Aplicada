import { useEffect, useId, useState } from "react";

import { API_BASE_URL } from "../api/config";
import {
  createComparison,
  type ComparisonAxis,
  type ComparisonResponse,
} from "../api/comparisons";
import { ApiRequestError } from "../api/http";
import { listProcessedSessions, type ProcessedSession } from "../api/processedSessions";
import { AppShell } from "../components/AppShell";
import { Link } from "../components/Link";
import ruled from "../styles/ruled.module.css";

import styles from "./ComparisonPage.module.css";

interface ComparisonPageProps {
  apiBaseUrl?: string;
}

function message(reason: unknown): string {
  return reason instanceof ApiRequestError
    ? reason.error.message
    : "No se pudo completar la comparación.";
}

function cellText(value: number | null, availability: string): string {
  if (availability !== "available" || value === null) return "No disponible";
  return String(value);
}

export function ComparisonPage({ apiBaseUrl = API_BASE_URL }: ComparisonPageProps) {
  const zoneId = useId();
  const axisId = useId();
  const [rows, setRows] = useState<ProcessedSession[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [zoneName, setZoneName] = useState("Local");
  const [axis, setAxis] = useState<ComparisonAxis>("session");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ComparisonResponse | null>(null);

  useEffect(() => {
    let active = true;
    listProcessedSessions(apiBaseUrl)
      .then((list) => {
        if (active) setRows(list);
      })
      .catch((reason: unknown) => {
        if (active) setLoadError(message(reason));
      });
    return () => {
      active = false;
    };
  }, [apiBaseUrl]);

  const eligible =
    rows?.filter(
      (row) =>
        row.result_complete &&
        row.status === "completed" &&
        row.source_kind !== "webcam",
    ) ?? [];

  function toggle(sessionId: string): void {
    setSelected((current) =>
      current.includes(sessionId)
        ? current.filter((id) => id !== sessionId)
        : [...current, sessionId],
    );
  }

  async function runComparison(): Promise<void> {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const body = await createComparison(apiBaseUrl, {
        session_ids: selected,
        zone_name: zoneName.trim(),
        axis,
      });
      setResult(body);
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell title="Comparaciones e insights">
      <section className={styles.section} aria-labelledby="comparison-title">
        <h1 id="comparison-title">Comparar sesiones</h1>
        <p>
          Elegí al menos dos sesiones de archivo completadas y una zona. Las cifras se leen del
          historial; no se recalculan desde el video.
        </p>
        <p>
          <Link href="/">Volver a las sesiones</Link>
        </p>

        {loadError !== null && <p role="alert">{loadError}</p>}
        {rows === null && loadError === null && <p role="status">Cargando historial…</p>}

        {rows !== null && (
          <div className={styles.controls}>
            <fieldset className={styles.sessionList}>
              <legend>Sesiones elegibles</legend>
              {eligible.length === 0 && <p>No hay sesiones de archivo completadas para comparar.</p>}
              {eligible.map((row) => (
                <label key={row.session_id}>
                  <input
                    type="checkbox"
                    checked={selected.includes(row.session_id)}
                    onChange={() => toggle(row.session_id)}
                  />{" "}
                  {row.name}
                  {row.finished_at !== null && (
                    <>
                      {" "}
                      <time dateTime={row.finished_at}>
                        ({new Date(row.finished_at).toLocaleDateString()})
                      </time>
                    </>
                  )}
                </label>
              ))}
            </fieldset>

            <div className={styles.actions}>
              <label htmlFor={zoneId}>
                Nombre de zona
                <input
                  id={zoneId}
                  value={zoneName}
                  onChange={(event) => setZoneName(event.target.value)}
                />
              </label>
              <label htmlFor={axisId}>
                Eje
                <select
                  id={axisId}
                  value={axis}
                  onChange={(event) => setAxis(event.target.value as ComparisonAxis)}
                >
                  <option value="session">Sesión vs sesión</option>
                  <option value="day">Día (cierre UTC del análisis)</option>
                  <option value="time_of_day">Horario (tiempo de video)</option>
                  <option value="zone">Zona (misma cámara)</option>
                </select>
              </label>
              <button
                type="button"
                disabled={busy || selected.length < 2 || zoneName.trim() === ""}
                onClick={() => void runComparison()}
              >
                {busy ? "Comparando…" : "Comparar"}
              </button>
            </div>
            {axis === "day" && (
              <p role="note">
                El eje día usa la fecha UTC de cierre del análisis, no el día del local ni el tiempo
                del video.
              </p>
            )}
            {selected.length < 2 && (
              <p role="status">Seleccioná al menos dos sesiones elegibles.</p>
            )}
          </div>
        )}

        {error !== null && <p role="alert">{error}</p>}

        {result !== null && (
          <>
            <div className={styles.tableWrap} role="region" aria-label="Tabla de comparación">
              <table className={ruled.table}>
                <thead>
                  <tr>
                    <th scope="col">Cifra</th>
                    {result.columns.map((column) => (
                      <th key={column.key} scope="col">
                        {column.label}
                        {column.camera_label !== null && (
                          <span> · {column.camera_label}</span>
                        )}
                      </th>
                    ))}
                    <th scope="col">Relación</th>
                  </tr>
                </thead>
                <tbody>
                  {result.figures.map((figure) => (
                    <tr key={`${figure.family}:${figure.code}`}>
                      <th scope="row">{figure.label}</th>
                      {figure.cells.map((cell, index) => (
                        <td key={`${figure.code}-${index}`}>
                          {cellText(cell.value, cell.availability)}
                        </td>
                      ))}
                      <td>{figure.relation}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <section className={styles.insights} aria-labelledby="insights-title">
              <h2 id="insights-title">Insights</h2>
              <ul>
                {result.insights.map((insight) => (
                  <li key={insight.code + insight.message}>
                    {insight.message}
                    {insight.estimation ? " (estimación)" : ""}
                  </li>
                ))}
              </ul>
            </section>
          </>
        )}
      </section>
    </AppShell>
  );
}
