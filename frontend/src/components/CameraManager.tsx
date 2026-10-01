import { useEffect, useState, type FormEvent } from "react";

import { deleteCamera, listCameras, renameCamera } from "../api/cameras";
import { ApiRequestError } from "../api/http";
import type { Camera } from "../types/session";
import styles from "./CameraManager.module.css";

interface CameraManagerProps {
  apiBaseUrl: string;
  onRenamed: (camera: Camera) => void;
  onBusyChange: (busy: boolean) => void;
}

function message(reason: unknown): string {
  return reason instanceof ApiRequestError ? reason.error.message : "No se pudo completar la operación.";
}

export function CameraManager({ apiBaseUrl, onRenamed, onBusyChange }: CameraManagerProps) {
  const [cameras, setCameras] = useState<Camera[] | null>(null);
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<Camera | null>(null);
  const [name, setName] = useState("");
  const [removing, setRemoving] = useState<Camera | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    listCameras(apiBaseUrl).then((result) => { if (active) setCameras(result); })
      .catch((reason: unknown) => { if (active) setError(message(reason)); });
    return () => { active = false; };
  }, [apiBaseUrl]);

  function setPending(value: boolean) { setBusy(value); onBusyChange(value); }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (editing === null || busy || name.trim() === "") return;
    setPending(true); setError(null); setNotice(null);
    try {
      const updated = await renameCamera(apiBaseUrl, editing.id, name.trim());
      setCameras((current) => current?.map((camera) => camera.id === updated.id ? updated : camera)
        .sort((a, b) => a.name.localeCompare(b.name)) ?? null);
      onRenamed(updated); setEditing(null); setSearch(""); setNotice("Nombre de la cámara actualizado.");
    } catch (reason) { setError(message(reason)); }
    finally { setPending(false); }
  }

  async function remove() {
    if (removing === null || busy) return;
    setPending(true); setError(null); setNotice(null);
    try {
      await deleteCamera(apiBaseUrl, removing.id);
      setCameras((current) => current?.filter((camera) => camera.id !== removing.id) ?? null);
      setNotice(`Se eliminó «${removing.name}» de las cámaras disponibles.`); setRemoving(null);
    } catch (reason) { setError(message(reason)); }
    finally { setPending(false); }
  }

  const visible = cameras?.filter((camera) => camera.name.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase())) ?? [];

  return <div className={styles.manager}>
    <p className={styles.description}>Actualizá los nombres o quitá las cámaras que ya no usás. Sus análisis y configuraciones se conservan.</p>
    <label className={styles.searchLabel} htmlFor="camera-search">Buscar cámara</label>
    <input id="camera-search" className={styles.search} type="search" value={search} disabled={busy}
      placeholder="Nombre de la cámara" onChange={(event) => setSearch(event.target.value)} />
    {error !== null && <p role="alert">{error}</p>}
    {notice !== null && <p role="status">{notice}</p>}
    {cameras === null && error === null && <p role="status">Cargando cámaras…</p>}
    {cameras !== null && visible.length === 0 && <p className={styles.empty}>{cameras.length === 0 ? "No hay cámaras registradas." : "No hay cámaras con ese nombre."}</p>}
    <ul className={styles.list} aria-label="Cámaras registradas">{visible.map((camera) => <li key={camera.id}>
      {editing?.id === camera.id ? <form className={styles.rename} onSubmit={(event) => void save(event)}>
        <label htmlFor={`camera-name-${camera.id}`}>Nombre de la cámara</label>
        <input id={`camera-name-${camera.id}`} value={name} maxLength={120} required disabled={busy} autoFocus
          onChange={(event) => setName(event.target.value)} />
        <div className={styles.buttons}><button type="button" disabled={busy} onClick={() => { setEditing(null); setError(null); }}>Cancelar</button>
          <button type="submit" disabled={busy || name.trim() === ""}>{busy ? "Guardando…" : "Guardar nombre"}</button></div>
      </form> : <div className={styles.row}>
        <div className={styles.camera}><strong>{camera.name}</strong><small>Registrada el {new Date(camera.created_at).toLocaleDateString("es-AR")}</small></div>
        <button className={styles.iconButton} type="button" disabled={busy} title="Editar nombre" aria-label={`Editar ${camera.name}`}
          onClick={() => { setEditing(camera); setName(camera.name); setRemoving(null); setError(null); setNotice(null); }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m16 3 5 5L8 21H3v-5L16 3ZM13 6l5 5" /></svg>
        </button>
        <button className={`${styles.iconButton} ${styles.trash}`} type="button" disabled={busy} title="Eliminar cámara" aria-label={`Eliminar ${camera.name}`}
          onClick={() => { setRemoving(camera); setEditing(null); setError(null); setNotice(null); }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M3 6h18M9 6V4h6v2M5 6l1 14h12l1-14M10 10v6M14 10v6" /></svg>
        </button>
      </div>}
      {removing?.id === camera.id && <div className={styles.confirm}>
        <strong>¿Eliminar «{camera.name}»?</strong>
        <p>No aparecerá al cargar nuevos videos. Los análisis anteriores siguen disponibles.</p>
        <div className={styles.buttons}><button type="button" disabled={busy} onClick={() => { setRemoving(null); setError(null); }}>Cancelar</button>
          <button className={styles.danger} type="button" disabled={busy} onClick={() => void remove()}>{busy ? "Eliminando…" : "Eliminar cámara"}</button></div>
      </div>}
    </li>)}</ul>
  </div>;
}
