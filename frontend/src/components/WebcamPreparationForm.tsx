import { useEffect, useId, useState, type FormEvent } from "react";
import { ApiRequestError } from "../api/http";
import { ArrowRight, ArrowRightLeft, Camera, Info, LogIn, MapPin, RefreshCw } from "lucide-react";
import { getLiveDevices, prepareWebcam } from "../api/live";
import type { LiveDevices } from "../types/live";
import { CameraPicker } from "./CameraPicker";
import styles from "./WebcamPreparationForm.module.css";

interface Props { apiBaseUrl: string; onPrepared: (sessionId: string) => void; }

export function WebcamPreparationForm({ apiBaseUrl, onPrepared }: Props) {
  const id = useId();
  const [name, setName] = useState("");
  const [camera, setCamera] = useState("");
  const [device, setDevice] = useState<number | null>(null);
  const [labelMode, setLabelMode] = useState<"directions" | "access">("directions");
  const [devices, setDevices] = useState<LiveDevices | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    setLoading(true); setError(null);
    getLiveDevices(apiBaseUrl).then(value => {
      if (!active) return;
      setDevices(value);
      setDevice(previous => previous === null ? value.candidates[0]?.device_index ?? null :
        value.candidates.some(item => item.device_index === previous) ? previous : null);
    }, reason => {
      if (active) { setDevices(null); setDevice(null); setError(reason instanceof ApiRequestError ? reason.message : "No se pudieron consultar las webcams."); }
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [apiBaseUrl, refresh]);
  const validDevice = device !== null && devices?.candidates.some(item => item.device_index === device);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy || loading || !devices?.worker_available || !validDevice || device === null || !name.trim() || !camera) return;
    setBusy(true); setError(null);
    try {
      const session = await prepareWebcam(apiBaseUrl, { name: name.trim(), registered_camera_id: camera,
        device_index: device, label_mode: labelMode });
      onPrepared(session.id);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo preparar la webcam."); }
    finally { setBusy(false); }
  }
  return <form className={styles.form} onSubmit={submit}>
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
    <section className={styles.column} aria-labelledby={id + "capture-title"}>
    <h2 id={id + "capture-title"}><Camera size={18} aria-hidden="true" />Dispositivo de captura</h2>
    <div className={styles.deviceRow}><div className={styles.field}>
    <label htmlFor={id + "device"}>Webcam</label><select id={id + "device"} disabled={loading || busy} value={device ?? ""} onChange={event => setDevice(event.target.value === "" ? null : Number(event.target.value))}>
      <option value="">Elegí una webcam</option>
      {devices?.candidates.map(item => <option key={item.device_index} value={item.device_index}>{item.label}{devices.candidates.filter(other => other.label === item.label).length > 1 ? ` (${item.device_index + 1})` : ""}</option>)}
    </select>
    </div>
    <button className={styles.refresh} type="button" aria-label="Actualizar dispositivos" title="Actualizar dispositivos" disabled={loading || busy} onClick={() => setRefresh(value => value + 1)}><RefreshCw size={18} aria-hidden="true" /></button>
    </div>
    {loading && <p role="status">Buscando cámaras…</p>}
    {!loading && devices?.candidates.length === 0 && <p role="status">No se detectaron webcams. Conectá una y actualizá la lista.</p>}
    <fieldset className={styles.crossings} disabled={busy} aria-describedby={id + "labels-help"}>
      <legend>Etiquetas de cruces</legend>
      <div className={styles.segmented}>
        <button type="button" aria-pressed={labelMode === "directions"} onClick={() => setLabelMode("directions")}><ArrowRightLeft size={16} aria-hidden="true" /><span>Sentidos A → B / B → A</span></button>
        <button type="button" aria-pressed={labelMode === "access"} onClick={() => setLabelMode("access")}><LogIn size={16} aria-hidden="true" /><span>Entradas / Salidas</span></button>
      </div>
      <p id={id + "labels-help"} className={styles.help}>Define cómo se clasificarán las direcciones de paso en las líneas.</p>
    </fieldset>
    {devices && !devices.worker_available && <p role="status">Las webcams están listadas. Iniciá el procesamiento local para preparar el análisis.</p>}
    </section>
    <section className={styles.column} aria-labelledby={id + "session-title"}>
    <h2 id={id + "session-title"}>Datos del análisis</h2>
    <div className={styles.field}><label htmlFor={id + "name"}>Nombre de la sesión</label><input id={id + "name"} placeholder="Ej. Acceso Principal - Turno Tarde" disabled={busy} required maxLength={120} value={name} onChange={event => setName(event.target.value)} /></div>
    <fieldset className={styles.location} disabled={busy}><legend className="sr-only">Asignación de ubicación</legend><MapPin className={styles.locationIcon} size={16} aria-hidden="true" /><CameraPicker apiBaseUrl={apiBaseUrl} value={camera} onChange={setCamera} compact terminology="location" label="Ubicación asignada" disclosureLabel="+ Agregar nueva ubicación" /></fieldset>
    </section>
    </div>
    {error && <p role="alert">{error}</p>}
    <div className={styles.actions}><p><Info size={17} aria-hidden="true" /><span>Se capturará un fotograma de referencia para calibrar las zonas de análisis.</span></p>
    <button className={styles.primary} type="submit" disabled={busy || loading || !devices?.worker_available || !validDevice || !name.trim() || !camera}>{busy ? "Preparando…" : "Preparar webcam y continuar"}<ArrowRight size={17} aria-hidden="true" /></button>
    </div>
  </form>;
}
