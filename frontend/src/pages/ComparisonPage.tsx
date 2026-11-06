import { useEffect, useId, useState } from "react";

import { API_BASE_URL } from "../api/config";
import { createComparison, type ComparisonResponse } from "../api/comparisons";
import { ApiRequestError } from "../api/http";
import { getSceneShops } from "../api/metrics";
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

function zoneOptions(names: string[]): string[] {
  const seen = new Map<string, string>();
  for (const raw of names) {
    const name = raw.trim();
    if (name === "") continue;
    const key = name.toLocaleLowerCase("es");
    if (!seen.has(key)) seen.set(key, name);
  }
  return [...seen.values()].sort((left, right) => left.localeCompare(right, "es"));
}

function preferredZone(names: string[]): string {
  const counts = new Map<string, { name: string; count: number }>();
  for (const raw of names) {
    const name = raw.trim();
    if (name === "") continue;
    const key = name.toLocaleLowerCase("es");
    const current = counts.get(key);
    if (current === undefined) counts.set(key, { name, count: 1 });
    else current.count += 1;
  }
  const ranked = [...counts.values()].sort(
    (left, right) => right.count - left.count || left.name.localeCompare(right.name, "es"),
  );
  return ranked[0]?.name ?? "";
}

export function ComparisonPage({ apiBaseUrl = API_BASE_URL }: ComparisonPageProps) {
  const zoneId = useId();
  const [rows, setRows] = useState<ProcessedSession[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [zoneName, setZoneName] = useState("");
  const [zoneNames, setZoneNames] = useState<string[]>([]);
  const [zonesReady, setZonesReady] = useState(false);
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

  useEffect(() => {
    if (rows === null) return;
    const versionIds = [
      ...new Set(
        rows
          .filter(
            (row) =>
              row.result_complete &&
              row.status === "completed" &&
              row.scene_version_id !== null,
          )
          .map((row) => row.scene_version_id as string),
      ),
    ];
    let active = true;
    setZonesReady(false);
    Promise.all(
      versionIds.map((id) =>
        getSceneShops(apiBaseUrl, id).then(
          (shops) => shops.map((shop) => shop.name),
          () => [] as string[],
        ),
      ),
    ).then((lists) => {
      if (!active) return;
      const collected = lists.flat();
      const names = zoneOptions(collected);
      setZoneNames(names);
      setZoneName((current) => {
        const key = current.trim().toLocaleLowerCase("es");
        return (
          names.find((name) => name.toLocaleLowerCase("es") === key) ?? preferredZone(collected)
        );
      });
      setZonesReady(true);
    });
    return () => {
      active = false;
    };
  }, [apiBaseUrl, rows]);

  const eligible =
    rows?.filter((row) => row.result_complete && row.status === "completed") ?? [];
  const selectedRows = eligible.filter((row) => selected.includes(row.session_id));
  const selectedOrigins = new Set(
    selectedRows.map((row) => (row.source_kind === "webcam" ? "webcam" : "file")),
  );
  const mixedOrigins = selectedOrigins.size > 1;

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
        axis: "session",
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
          Elegí al menos dos sesiones completadas del mismo origen y una zona. Los archivos se
          comparan entre sí y las sesiones en vivo entre sí. Las cifras se leen del historial.
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
              {eligible.length === 0 && <p>No hay sesiones completadas para comparar.</p>}
              {eligible.map((row) => (
                <label key={row.session_id}>
                  <input
                    type="checkbox"
                    checked={selected.includes(row.session_id)}
                    onChange={() => toggle(row.session_id)}
                  />{" "}
                  {row.name}
                  {row.source_kind === "webcam" && " · en vivo"}
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
                <select
                  id={zoneId}
                  value={zoneName}
                  disabled={!zonesReady || zoneNames.length === 0}
                  onChange={(event) => setZoneName(event.target.value)}
                >
                  {!zonesReady && <option value="">Cargando zonas…</option>}
                  {zonesReady && zoneNames.length === 0 && <option value="">Sin zonas</option>}
                  {zoneNames.map((name) => (
                    <option key={name} value={name}>
                      {name}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                disabled={busy || selected.length < 2 || mixedOrigins || zoneName.trim() === ""}
                onClick={() => void runComparison()}
              >
                {busy ? "Comparando…" : "Comparar"}
              </button>
            </div>
            {mixedOrigins && (
              <p role="status">Compará sesiones en vivo entre sí, o archivos entre sí.</p>
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
