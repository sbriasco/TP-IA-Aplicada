import { useEffect, useId, useState } from "react";
import styles from "./CameraPicker.module.css";

import { createCamera, listCameras } from "../api/cameras";
import { ApiRequestError } from "../api/http";
import type { Camera } from "../types/session";

interface CameraPickerProps {
  apiBaseUrl: string;
  value: string;
  onChange: (cameraId: string) => void;
  compact?: boolean;
  terminology?: "camera" | "location";
  label?: string;
  createLegend?: string;
}

function errorMessage(error: unknown): string {
  return error instanceof ApiRequestError ? error.error.message : "Ocurrió un error inesperado.";
}

function byName(a: Camera, b: Camera): number {
  return a.name.localeCompare(b.name);
}

export function CameraPicker({ apiBaseUrl, value, onChange, compact = false, terminology = "camera", label, createLegend }: CameraPickerProps) {
  const location = terminology === "location";
  const id = useId();
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    listCameras(apiBaseUrl)
      .then((result) => {
        if (active) setCameras(result);
      })
      .catch((error: unknown) => {
        if (active) setLoadError(errorMessage(error));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [apiBaseUrl]);

  async function handleCreate() {
    const name = newName.trim();
    if (name === "" || creating) return;
    setCreating(true);
    setNotice(null);
    setCreateError(null);
    try {
      const { camera, existed } = await createCamera(apiBaseUrl, name);
      setCameras((current) =>
        current.some((item) => item.id === camera.id) ? current : [...current, camera].sort(byName),
      );
      onChange(camera.id);
      setNewName("");
      setNotice(
        existed
          ? `Ya existía la ${location ? "ubicación" : "cámara"} «${camera.name}»; quedó seleccionada.`
          : `${location ? "Ubicación" : "Cámara"} «${camera.name}» creada y seleccionada.`,
      );
    } catch (error) {
      setCreateError(errorMessage(error));
    } finally {
      setCreating(false);
    }
  }

  const createFields = (
      <fieldset className={styles.create}>
        <legend>{createLegend ?? (location ? "Nueva ubicación" : "Nueva cámara")}</legend>
        <label htmlFor={`${id}-new-camera`}>{location ? "Nombre de la ubicación" : "Nombre de la cámara"}</label>
        <input id={`${id}-new-camera`} value={newName} maxLength={120} placeholder={location ? "Por ejemplo: Entrada principal" : undefined}
          onChange={(event) => setNewName(event.target.value)}
          onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); void handleCreate(); } }} />
        <button type="button" onClick={() => void handleCreate()} disabled={creating || newName.trim() === ""}>{location ? "Crear ubicación" : "Crear cámara"}</button>
        {notice !== null && <p role="status">{notice}</p>}
        {createError !== null && <p role="alert">{createError}</p>}
      </fieldset>
  );
  return (
    <div className={styles.picker}>
      <label htmlFor={`${id}-camera`}>{label ?? (location ? "Ubicación del análisis" : "Cámara")}</label>
      <select
        id={`${id}-camera`}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={loading}
        required
      >
        <option value="">{loading ? (location ? "Cargando ubicaciones…" : "Cargando cámaras…") : (location ? "Elegí una ubicación" : "Elegí una cámara")}</option>
        {cameras.map((camera) => (
          <option key={camera.id} value={camera.id}>
            {camera.name}
          </option>
        ))}
      </select>
      {loadError !== null && <p role="alert">{loadError}</p>}

      {compact ? <details className={styles.disclosure}><summary>{location ? "Agregar una ubicación" : "Agregar una cámara"}</summary>{createFields}</details> : createFields}
    </div>
  );
}
