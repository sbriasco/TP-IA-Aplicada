import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { LivePreparationPage } from "../src/pages/LivePreparationPage";
import { byButton, byLabel, changeValue, click } from "./dom";

const camera = { id: "camera-1", name: "Expo", created_at: "2026-10-03T00:00:00Z" };
const session = { id: "session-1", name: "Stand", source_kind: "webcam", camera,
  camera_id: "camera-1", created_at: camera.created_at, video: null,
  reference_frame: { frame_index: 0, video_timestamp_seconds: 0, width: 1280, height: 720,
    url: "/sessions/session-1/reference-frame" }, duplicate_session_ids: [],
  live_source: { machine_id: "expo-test", device_index: 0, capture_backend: "dshow",
    width: 1280, height: 720, label_mode: "directions", reported_fps: 30,
    prepared_at: camera.created_at, frame_checked_at: null } };
let root: Root;
let container: HTMLDivElement;
const response = (body: unknown) => ({ ok: true, status: 200, text: async () => JSON.stringify(body) });
beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  container = document.createElement("div"); document.body.append(container); root = createRoot(container);
  window.history.replaceState(null, "", "/live");
});
afterEach(async () => { await act(async () => root.unmount()); container.remove(); vi.unstubAllGlobals(); });

it("prepara el dispositivo seleccionado por nombre aunque no sea el índice cero", async () => {
  let selected: number | undefined;
  let labelMode: string | undefined;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith("/live/sessions")) {
      const payload = JSON.parse(String(init?.body)) as { device_index: number; label_mode: string };
      selected = payload.device_index;
      labelMode = payload.label_mode;
    }
    return response(url.endsWith("/cameras") ? [camera] : url.endsWith("/live/devices") ?
      { machine_id: "expo-test", worker_available: true, candidates: [
        { device_index: 0, label: "Integrated Camera", verified: false },
        { device_index: 1, label: "Logitech USB", verified: false }] } : session);
  }));
  await act(async () => root.render(<LivePreparationPage apiBaseUrl="http://api.test" />));
  await changeValue(byLabel<HTMLInputElement>(container, "Nombre de la sesión"), "Stand");
  await changeValue(byLabel<HTMLSelectElement>(container, "Ubicación asignada"), camera.id);
  await changeValue(byLabel<HTMLSelectElement>(container, "Webcam"), "1");
  await click(byButton(container, "Entradas / Salidas"));
  await click(byButton(container, "Preparar webcam y continuar"));
  expect(selected).toBe(1);
  expect(labelMode).toBe("access");
  expect(window.location.pathname).toBe("/sessions/session-1/live");
});

it("actualiza las cámaras conectadas y no prepara un dispositivo que fue retirado", async () => {
  let cameras = [{ device_index: 0, label: "Integrated Camera", verified: false },
    { device_index: 1, label: "Logitech USB", verified: false }];
  vi.stubGlobal("fetch", vi.fn(async (url: string) => response(url.endsWith("/cameras") ? [camera] :
    url.endsWith("/live/devices") ? { machine_id: "expo-test", worker_available: true, candidates: cameras } : session)));
  await act(async () => root.render(<LivePreparationPage apiBaseUrl="http://api.test" />));
  await changeValue(byLabel<HTMLInputElement>(container, "Nombre de la sesión"), "Stand");
  await changeValue(byLabel<HTMLSelectElement>(container, "Ubicación asignada"), camera.id);
  await changeValue(byLabel<HTMLSelectElement>(container, "Webcam"), "1");
  cameras = [{ device_index: 0, label: "Integrated Camera", verified: false }];
  await click(container.querySelector<HTMLButtonElement>('button[aria-label="Actualizar dispositivos"]')!);
  expect(container.textContent).not.toContain("Logitech USB");
  expect(byButton(container, "Preparar webcam y continuar").disabled).toBe(true);
});

it("sin webcams conectadas muestra estado vacío y bloquea preparación", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => response(url.endsWith("/cameras") ? [camera] :
    { machine_id: "expo-test", worker_available: true, candidates: [] })));
  await act(async () => root.render(<LivePreparationPage apiBaseUrl="http://api.test" />));
  await changeValue(byLabel<HTMLInputElement>(container, "Nombre de la sesión"), "Stand");
  await changeValue(byLabel<HTMLSelectElement>(container, "Ubicación asignada"), camera.id);
  expect(container.textContent).toContain("No se detectaron webcams");
  expect(byButton(container, "Preparar webcam y continuar").disabled).toBe(true);
});

it("prepara una webcam sin grabación y permite abrir el editor", async () => {
  const fetchMock = vi.fn(async (url: string) => response(url.endsWith("/cameras") ? [camera] :
    url.endsWith("/live/devices") ? { machine_id: "expo-test", worker_available: true,
      candidates: [{ device_index: 0, label: "Webcam 0", verified: false }] } : session));
  vi.stubGlobal("fetch", fetchMock);
  await act(async () => root.render(<LivePreparationPage apiBaseUrl="http://api.test" />));
  await changeValue(byLabel<HTMLInputElement>(container, "Nombre de la sesión"), "Stand");
  await changeValue(byLabel<HTMLSelectElement>(container, "Ubicación asignada"), camera.id);
  await click(byButton(container, "Preparar webcam y continuar"));
  expect(window.location.pathname).toBe("/sessions/session-1/live");
  const call = fetchMock.mock.calls.find(([url]) => url.endsWith("/live/sessions"));
  expect(call).toBeDefined();
  expect(container.textContent).toContain("No se almacenará video grabado");
});

it("exige comprobar y confirmar el encuadre antes de iniciar", async () => {
  const fetchMock = vi.fn(async (url: string) => response(
    url.endsWith("/scene-versions") ? [{ id: "scene-1", version_number: 1 }] :
    url.endsWith("/live/check") ? { check_token: "check-token", expires_in_seconds: 60,
      width: 1280, height: 720, image_media_type: "image/jpeg", image_base64: "eA==", backend: "dshow" } :
    url.endsWith("/live/start") ? { id: "job-1", kind: "live_analysis", status: "pending" } : session));
  vi.stubGlobal("fetch", fetchMock);
  await act(async () => root.render(<LivePreparationPage sessionId="session-1" apiBaseUrl="http://api.test" />));
  expect(byButton(container, "Iniciar análisis en vivo").disabled).toBe(true);
  expect(container.querySelector('a[href="/sessions/session-1/editor"]')).not.toBeNull();
  await click(byButton(container, "Comprobar encuadre"));
  expect(byButton(container, "Iniciar análisis en vivo").disabled).toBe(true);
  await click(byLabel<HTMLInputElement>(container, "Confirmo que este es el encuadre actual"));
  await click(byButton(container, "Iniciar análisis en vivo"));
  expect(window.location.pathname).toBe("/live/jobs/job-1");
});
