import { useEffect, useState, type FormEvent } from "react";

import { Play, Trash2, Layers, Cpu } from "lucide-react";

import { ApiRequestError } from "../api/http";
import { aspectRatioMismatch, createVideoAnalysisJob, deleteSceneVersion, listSceneVersions } from "../api/scenes";
import type { AnalysisJob, AspectRatios, SceneVersionSummary } from "../types/scene";
import type { SessionDetail } from "../types/session";
import { Link } from "./Link";
import { Modal } from "./Modal";
import { SceneConfigurationSelect } from "./SceneConfigurationSelect";

import styles from "./StartAnalysisSection.module.css";

type VersionsState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "loaded"; versions: SceneVersionSummary[] };

type AnalysisOutcome =
  | { kind: "created"; job: AnalysisJob; version: SceneVersionSummary | undefined }
  | { kind: "scene_not_configured"; message: string }
  | { kind: "aspect_ratio_mismatch"; message: string; ratios: AspectRatios | null }
  | { kind: "error"; message: string };

interface StartAnalysisSectionProps {
  apiBaseUrl: string;
  session: SessionDetail;
  onConfigurationChange?: (versionId: string) => void;
  onVersionChange?: (version: SceneVersionSummary | undefined) => void;
}

function errorMessage(reason: unknown): string {
  return reason instanceof ApiRequestError ? reason.error.message : "Ocurrió un error inesperado.";
}

export function StartAnalysisSection({ apiBaseUrl, session, onConfigurationChange, onVersionChange }: StartAnalysisSectionProps) {
  const [versions, setVersions] = useState<VersionsState>({ kind: "loading" });
  const [selectedId, setSelectedId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [outcome, setOutcome] = useState<AnalysisOutcome | null>(null);
  const [toRemove, setToRemove] = useState<SceneVersionSummary | null>(null);
  const [removing, setRemoving] = useState(false);
  const [removeError, setRemoveError] = useState<string | null>(null);
  const [removeNotice, setRemoveNotice] = useState<string | null>(null);

  useEffect(() => { onConfigurationChange?.(selectedId); }, [selectedId, onConfigurationChange]);

  useEffect(() => {
    let active = true;
    setVersions({ kind: "loading" });
    setSelectedId("");
    setOutcome(null);
    setToRemove(null);
    setRemoveError(null);
    setRemoveNotice(null);
    listSceneVersions(apiBaseUrl, session.camera.id)
      .then((loaded) => {
        if (!active) return;
        const sorted = [...loaded].sort((a, b) => b.version_number - a.version_number);
        setVersions({ kind: "loaded", versions: sorted });
        setSelectedId(sorted[0]?.id ?? "");
      })
      .catch((reason: unknown) => {
        if (active) setVersions({ kind: "error", message: errorMessage(reason) });
      });
    return () => { active = false; };
  }, [apiBaseUrl, session.camera.id, session.id]);

  useEffect(() => { onVersionChange?.(versions.kind === "loaded" ? versions.versions.find(version => version.id === selectedId) : undefined); }, [versions, selectedId, onVersionChange]);

  const editorHref = `/sessions/${encodeURIComponent(session.id)}/editor`;

  async function removeConfiguration() {
    if (toRemove === null || removing || versions.kind !== "loaded") return;
    setRemoving(true); setRemoveError(null); setRemoveNotice(null);
    try {
      await deleteSceneVersion(apiBaseUrl, toRemove.id);
      const remaining = versions.versions.filter((version) => version.id !== toRemove.id);
      setVersions({ kind: "loaded", versions: remaining });
      if (selectedId === toRemove.id) setSelectedId(remaining[0]?.id ?? "");
      setOutcome(null); setToRemove(null);
      setRemoveNotice(`Se eliminó la configuración ${toRemove.version_number}. Los análisis anteriores se conservan.`);
    } catch (reason) { setRemoveError(errorMessage(reason)); }
    finally { setRemoving(false); }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting || removing || versions.kind !== "loaded" || selectedId === "") return;
    setSubmitting(true);
    setOutcome(null);
    try {
      const job = await createVideoAnalysisJob(apiBaseUrl, session.id, selectedId);
      const version = versions.versions.find((item) => item.id === job.scene_version_id);
      setOutcome({ kind: "created", job, version });
    } catch (reason) {
      if (reason instanceof ApiRequestError && reason.error.code === "scene_not_configured") {
        setOutcome({ kind: "scene_not_configured", message: reason.error.message });
      } else if (reason instanceof ApiRequestError && reason.error.code === "aspect_ratio_mismatch") {
        setOutcome({ kind: "aspect_ratio_mismatch", message: reason.error.message, ratios: aspectRatioMismatch(reason.error) });
      } else {
        setOutcome({ kind: "error", message: errorMessage(reason) });
      }
    } finally {
      setSubmitting(false);
    }
  }

  let body;
  if (versions.kind === "loading") {
    body = <p role="status">Cargando configuraciones…</p>;
  } else if (versions.kind === "error") {
    body = <p role="alert">{versions.message}</p>;
  } else if (versions.versions.length === 0) {
    body = <div className={styles.empty}>
      <strong>Primero, marcá qué querés medir</strong>
      <p>La cámara {session.camera.name} no tiene ninguna configuración de escena. Dibujá los zonas de análisis y accesos sobre la imagen del video.</p>
      <Link className={styles.editorLink} href={editorHref}>Abrir el editor de escena</Link>
    </div>;
  } else {
    const selectedVersion = versions.versions.find((item) => item.id === selectedId);
    body = <form onSubmit={handleSubmit}>
      <label className={styles.label} htmlFor="analysis-configuration">Configuración de escena</label>
      <div className={styles.selectorRow}>
        <SceneConfigurationSelect id="analysis-configuration" versions={versions.versions} value={selectedId} disabled={submitting || removing}
          onChange={id => { setSelectedId(id); setOutcome(null); }} />
        {selectedVersion && <button className={styles.deleteConfiguration} type="button" disabled={submitting || removing}
          aria-label={`Eliminar configuración ${selectedVersion.version_number}`} title="Eliminar configuración"
          onClick={() => { setToRemove(selectedVersion); setRemoveError(null); }}><Trash2 size={16} aria-hidden="true" /></button>}
      </div>
      <p className={styles.explanation} id="configuration-explanation">Las métricas se procesarán utilizando los polígonos de esta versión.</p>
      <div className={styles.quickStats}>
        <div><span><Layers size={14} aria-hidden="true" /> Zonas definidas</span><strong>{selectedVersion?.shop_count ?? 0} {selectedVersion?.shop_count === 1 ? "zona de interés" : "zonas de interés"}</strong></div>
        <div><span><Cpu size={14} aria-hidden="true" /> Dispositivo de inferencia</span><strong>Worker local</strong></div>
      </div>
      <button className={styles.startButton} type="submit" disabled={submitting || removing || selectedId === ""}>
        <Play size={18} aria-hidden="true" />{submitting ? "Iniciando…" : "Iniciar análisis de video"}
      </button>
      {outcome?.kind === "created" && <p className={styles.feedback} role="status">
        Análisis en cola{outcome.version !== undefined && ` con la configuración ${outcome.version.version_number}`}.
        El procesamiento comenzará cuando el equipo esté disponible.{" "}
        <Link href={`/?job=${encodeURIComponent(outcome.job.id)}`}>Ver avance del análisis</Link>
      </p>}
      {outcome?.kind === "scene_not_configured" && <p className={styles.feedback} role="alert">
        {outcome.message} <Link href={editorHref}>Abrir el editor de escena</Link>
      </p>}
      {outcome?.kind === "aspect_ratio_mismatch" && <p className={styles.feedback} role="alert">
        {outcome.ratios !== null && selectedVersion !== undefined
          ? `El formato del video (${outcome.ratios.video.toFixed(3)}) no coincide con el de la configuración ${selectedVersion.version_number} (${outcome.ratios.version.toFixed(3)}). Guardá una configuración nueva sobre la imagen de este video.`
          : outcome.message}{" "}<Link href={editorHref}>Abrir el editor de escena</Link>
      </p>}
      {outcome?.kind === "error" && <p className={styles.feedback} role="alert">{outcome.message}</p>}
    </form>;
  }

  return <section aria-labelledby="analysis-title">
    <h2 id="analysis-title">Iniciar análisis</h2>
    {removeNotice !== null && <p className={styles.feedback} role="status">{removeNotice}</p>}
    {body}
    {toRemove !== null && <Modal title="Eliminar configuración" busy={removing} onClose={() => setToRemove(null)}>
      <p>¿Eliminar la <strong>configuración {toRemove.version_number}</strong>?</p>
      <p className={styles.explanation}>Dejará de aparecer para nuevos análisis. Se conservan los resultados anteriores y la configuración que usaron.</p>
      {removeError !== null && <p role="alert">{removeError}</p>}
      <div className={styles.confirmActions}><button type="button" disabled={removing} onClick={() => setToRemove(null)}>Cancelar</button>
        <button type="button" className={styles.confirmDelete} disabled={removing} onClick={() => void removeConfiguration()}>{removing ? "Eliminando…" : "Eliminar configuración"}</button></div>
    </Modal>}
  </section>;
}
