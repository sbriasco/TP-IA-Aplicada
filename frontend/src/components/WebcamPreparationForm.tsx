import { useEffect, useId, useState, type FormEvent } from "react";
import { ApiRequestError } from "../api/http";
import { getLiveDevices, prepareWebcam } from "../api/live";
import type { LiveDevices } from "../types/live";
import { CameraPicker } from "./CameraPicker";

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
  return <form onSubmit={submit}>
    <p>Sin grabación. Se conserva una imagen de referencia para configurar la escena.</p>
    <label htmlFor={id + "name"}>Nombre de la sesión</label><input id={id + "name"} required maxLength={120} value={name} onChange={event => setName(event.target.value)} />
    <CameraPicker apiBaseUrl={apiBaseUrl} value={camera} onChange={setCamera} />
    <label htmlFor={id + "device"}>Webcam</label><select id={id + "device"} disabled={loading || busy} value={device ?? ""} onChange={event => setDevice(event.target.value === "" ? null : Number(event.target.value))}>
      <option value="">Elegí una webcam</option>
      {devices?.candidates.map(item => <option key={item.device_index} value={item.device_index}>{item.label}{devices.candidates.filter(other => other.label === item.label).length > 1 ? ` (${item.device_index + 1})` : ""}</option>)}
    </select>
    <button type="button" disabled={loading || busy} onClick={() => setRefresh(value => value + 1)}>Actualizar cámaras</button>
    {loading && <p role="status">Buscando cámaras…</p>}
    {!loading && devices?.candidates.length === 0 && <p role="status">No se detectaron webcams. Conectá una y actualizá la lista.</p>}
    <label htmlFor={id + "labels"}>Etiquetas de los cruces</label><select id={id + "labels"} value={labelMode} onChange={event => setLabelMode(event.target.value === "access" ? "access" : "directions")}>
      <option value="directions">Sentidos A → B / B → A</option><option value="access">Entradas / salidas de un acceso</option>
    </select>
    {devices && !devices.worker_available && <p role="status">El worker de webcam no está disponible. Inicialo y volvé a esta pantalla.</p>}
    {error && <p role="alert">{error}</p>}
    <button type="submit" disabled={busy || loading || !devices?.worker_available || !validDevice || !name.trim() || !camera}>{busy ? "Preparando…" : "Preparar webcam"}</button>
  </form>;
}
