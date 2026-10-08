import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { LiveAnalysisPage } from "../src/pages/LiveAnalysisPage";
import { byButton, byLabel, changeValue, click } from "./dom";

vi.mock("../src/components/CrossingChart", () => ({ CrossingChart: () => <p>Gráfico de cruces</p> }));
class Socket {
  static instances: Socket[] = [];
  readyState = 1;
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  send = vi.fn();
  close = vi.fn();
  constructor() { Socket.instances.push(this); }
  message(value: unknown) { this.onmessage?.({ data: JSON.stringify(value) }); }
}
const result = { job_id: "job-1", session_id: "session-1", source_kind: "webcam",
  status: "processing", capture_status: "connected", result_complete: false,
  coverage_complete: true, unknown_tail: false, elapsed_capture_seconds: 0,
  revision: 0, checkpoint_at: null, selected_shop_id: "shop-1",
  shops: [{ shop_id: "shop-1", shop_name: "Paso" }], summary: { shop_id: "shop-1",
    shop_name: "Paso", entry_count: 0, exit_count: 0, a_to_b_count: 0, b_to_a_count: 0,
    total_crossings: 0, label_mode: "directions", partial: true, entry_direction: "a_to_b" },
  minutes: [], next_bucket_cursor: null, interruptions: [], observed_seconds: 0,
  missing_seconds: 0, unconfirmed_crossings: 0, sampling: { time_basis: "capture", sample_count: 0,
    candidate_count: 0, capacity: 20000 } };
function update(revision: number, sequence: number, total: number, image: string) {
  return { type: "live.update", schema_version: "3", source_kind: "webcam", job_id: "job-1",
    session_id: "session-1", revision, capture_sequence: sequence, segment_index: 0,
    capture_status: "connected", capture_timestamp_seconds: sequence,
    captured_monotonic_ms: 1000, published_monotonic_ms: 1100, image_media_type: "image/jpeg",
    image_base64: image, partial: true, capture_fps: 30, analysis_fps: 10, capture_to_publish_ms: 100,
    shops: [{ ...result.summary, entry_count: total, a_to_b_count: total, total_crossings: total }],
    minutes: [], coverage_complete: true, checkpoint_revision: 0, checkpoint_at: null };
}
let root: Root, container: HTMLDivElement;
const response = (value: unknown) => ({ ok: true, status: 200, text: async () => JSON.stringify(value) });

function status(capture_status: string, revision: number) {
  return { type: "live.status", schema_version: "3", source_kind: "webcam",
    job_id: "job-1", session_id: "session-1", status: "processing", revision,
    capture_status, capture_timestamp_seconds: 5, coverage_complete: false, unknown_tail: false };
}
beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true); vi.stubGlobal("WebSocket", Socket);
  Socket.instances = []; container = document.createElement("div"); document.body.append(container);
  root = createRoot(container);
  vi.stubGlobal("fetch", vi.fn(async (url: string) => response(url.endsWith("/live/stop") ?
    { id: "job-1", session_id: "session-1", status: "processing", kind: "live_analysis" } : result)));
});
afterEach(async () => { await act(async () => root.unmount()); container.remove(); vi.useRealTimers(); vi.unstubAllGlobals(); });

it("espera el acuse de pausa y conserva conteos ante un frame atrasado", async () => {
  await act(async () => root.render(<LiveAnalysisPage jobId="job-1" apiBaseUrl="http://api.test" />));
  const socket = Socket.instances[0];
  await act(async () => socket.message(update(2, 5, 3, "eA==")));
  await click(byButton(container, "Pausar análisis"));
  expect(container.textContent).toContain("Pausando");
  expect(container.querySelector('button')?.textContent).not.toBe("Retomar análisis");
  await act(async () => socket.message(status("paused", 4)));
  expect(byButton(container, "Retomar análisis").disabled).toBe(false);
  await act(async () => socket.message(update(3, 6, 99, "eQ==")));
  expect(container.querySelector('[aria-label="Total de cruces"]')?.textContent).toBe("3");
  expect(container.textContent).toContain("Análisis pausado");
  expect(byButton(container, "Detener análisis").disabled).toBe(false);
});

it("recupera una pausa al recargar y exige un encuadre nuevo para retomar", async () => {
  vi.mocked(fetch).mockImplementation(async (url) => response(String(url).endsWith("/live/continue") ?
    { job_id: "job-1", resume_requested: true } : { ...result, capture_status: "paused", revision: 5 }) as Response);
  await act(async () => root.render(<LiveAnalysisPage jobId="job-1" apiBaseUrl="http://api.test" />));
  await click(byButton(container, "Retomar análisis"));
  expect(byButton(container, "Retomar análisis").disabled).toBe(true);
  expect(vi.mocked(fetch).mock.calls.filter(([url]) => String(url).endsWith("/live/continue"))).toHaveLength(1);
  expect(vi.mocked(fetch).mock.calls.some(([url]) => String(url).endsWith("/live/confirm-resume"))).toBe(false);
});

it("muestra el checkpoint final de pausa aunque el último frame no llegue", async () => {
  let paused = false;
  vi.mocked(fetch).mockImplementation(async () => response(paused ? { ...result,
    capture_status: "paused", revision: 4, coverage_complete: false,
    summary: { ...result.summary, entry_count: 6, a_to_b_count: 6, total_crossings: 6 },
    zone_dwell: { "shop-1": { front_average_seconds: 1.5, front_sample_count: 1,
      interior_average_seconds: null, interior_sample_count: 0 } },
  } : result) as Response);
  await act(async () => root.render(<LiveAnalysisPage jobId="job-1" apiBaseUrl="http://api.test" />));
  await act(async () => Socket.instances[0].message(update(2, 5, 3, "eA==")));
  paused = true;
  await act(async () => Socket.instances[0].message(status("paused", 4)));
  expect(container.querySelector('[aria-label="Total de cruces"]')?.textContent).toBe("6");
  expect(container.querySelector('[aria-label="Estadía promedio externa"]')?.textContent).toBe("1,5 s");
  expect(container.textContent).toContain("Cobertura incompleta");
});

it("consulta el checkpoint de pausa de la línea seleccionada", async () => {
  const second = { ...result.summary, shop_id: "shop-2", shop_name: "Segundo", entry_count: 6,
    a_to_b_count: 6, total_crossings: 6 };
  let paused = false;
  vi.mocked(fetch).mockImplementation(async (url) => response({ ...result,
    shops: [...result.shops, { shop_id: "shop-2", shop_name: "Segundo" }],
    capture_status: paused ? "paused" : "connected", revision: paused ? 4 : 0,
    selected_shop_id: String(url).includes("shop_id=shop-2") ? "shop-2" : "shop-1",
    summary: String(url).includes("shop_id=shop-2") ? second : result.summary,
  }) as Response);
  await act(async () => root.render(<LiveAnalysisPage jobId="job-1" apiBaseUrl="http://api.test" />));
  await act(async () => Socket.instances[0].message({ ...update(2, 5, 3, "eA=="), shops: [
    update(2, 5, 3, "eA==").shops[0], { ...second, entry_count: 5, a_to_b_count: 5, total_crossings: 5 },
  ] }));
  await changeValue(container.querySelector("select")!, "shop-2");
  paused = true;
  await act(async () => Socket.instances[0].message(status("paused", 4)));
  expect(container.querySelector('[aria-label="Total de cruces"]')?.textContent).toBe("6");
});

it("respeta Entrada/Salida en el vivo aunque entrada sea B a A", async () => {
  await act(async () => root.render(<LiveAnalysisPage jobId="job-1" apiBaseUrl="http://api.test" />));
  const frame = update(1, 1, 3, "eA==");
  await act(async () => Socket.instances[0].message({ ...frame, shops: [{ ...frame.shops[0],
    label_mode: "access", entry_direction: "b_to_a", entry_count: 2, exit_count: 1,
    a_to_b_count: 1, b_to_a_count: 2, total_crossings: 3 }] }));
  expect(container.querySelector('[aria-label="Entradas"]')?.textContent).toBe("2");
  expect(container.querySelector('[aria-label="Salidas"]')?.textContent).toBe("1");
  expect(container.querySelector('[aria-label="A → B"]')).toBeNull();
});

it("muestra estadías observadas y permite activar y apagar el mapa de calor", async () => {
  vi.mocked(fetch).mockImplementation(async (url) => response(String(url).endsWith("/position-samples") ? {
    job_id: "job-1", source_kind: "webcam", time_basis: "capture", availability: "available",
    samples: [{ capture_timestamp_seconds: 1, foot: [.2, .8] }],
  } : result) as Response);
  await act(async () => root.render(<LiveAnalysisPage jobId="job-1" apiBaseUrl="http://api.test" />));
  await act(async () => Socket.instances[0].message({ ...update(2, 5, 3, "eA=="),
    zone_dwell: { "shop-1": { interior_average_seconds: 12.5, front_average_seconds: null,
      interior_sample_count: 2, front_sample_count: 0 } } }));
  expect(container.querySelector('[aria-label="Estadía promedio interna"]')?.textContent).toBe("12,5 s");
  expect(container.querySelector('[aria-label="Estadía promedio externa"]')?.textContent).toBe("--");
  const checkbox = byLabel(container, "Superponer mapa de calor");
  await click(checkbox);
  expect(container.querySelector('svg[aria-label="Mapa de calor"]')).not.toBeNull();
  await click(checkbox);
  expect(container.querySelector('svg[aria-label="Mapa de calor"]')).toBeNull();
});

it("publica una sola medición después del pintado y declara reloj sin calibrar", async () => {
  const callbacks: FrameRequestCallback[] = [];
  vi.stubGlobal("requestAnimationFrame", vi.fn((callback: FrameRequestCallback) => { callbacks.push(callback); return callbacks.length; }));
  vi.stubGlobal("cancelAnimationFrame", vi.fn());
  const listener = vi.fn();
  window.addEventListener("flowsight:live-latency", listener);
  try {
    await act(async () => root.render(<LiveAnalysisPage jobId="job-1" apiBaseUrl="http://api.test" />));
    await act(async () => Socket.instances[0].message(update(2, 5, 3, "eA==")));
    const image = container.querySelector('img[alt="Cámara en vivo"]')!;
    await act(async () => image.dispatchEvent(new Event("load")));
    expect(listener).not.toHaveBeenCalled();
    await act(async () => callbacks.shift()!(100));
    expect(listener).not.toHaveBeenCalled();
    await act(async () => callbacks.shift()!(116));
    expect(listener).toHaveBeenCalledTimes(1);
    expect((listener.mock.calls[0][0] as CustomEvent).detail).toMatchObject({ measured: false, estimated_ms: null });
    await act(async () => image.dispatchEvent(new Event("load")));
    await act(async () => callbacks.shift()!(132));
    await act(async () => callbacks.shift()!(148));
    expect(listener).toHaveBeenCalledTimes(1);
  } finally { window.removeEventListener("flowsight:live-latency", listener); }
});

it("reintenta cuando también falla REST durante la reconexión", async () => {
  vi.useFakeTimers();
  await act(async () => root.render(<LiveAnalysisPage jobId="job-1" apiBaseUrl="http://api.test" />));
  const fetchMock = vi.mocked(fetch);
  fetchMock.mockRejectedValueOnce(new Error("Sin conexión"));
  await act(async () => Socket.instances[0].onclose?.());
  await act(async () => vi.advanceTimersByTimeAsync(1000));
  expect(Socket.instances).toHaveLength(1);
  await act(async () => vi.advanceTimersByTimeAsync(2000));
  expect(Socket.instances).toHaveLength(2);
});

it("reemplaza imagen y métricas juntas e ignora revisiones viejas o de otro trabajo", async () => {
  await act(async () => root.render(<LiveAnalysisPage jobId="job-1" apiBaseUrl="http://api.test" />));
  const socket = Socket.instances[0]; expect(socket).toBeDefined();
  await act(async () => socket.message(update(2, 5, 3, "eA==")));
  expect(container.querySelector('img[alt="Cámara en vivo"]')?.getAttribute("src")).toBe("data:image/jpeg;base64,eA==");
  expect(container.querySelector('[aria-label="Total de cruces"]')?.textContent).toBe("3");
  await act(async () => socket.message(update(1, 4, 99, "eQ==")));
  await act(async () => socket.message({ ...update(3, 6, 99, "eQ=="), job_id: "other" }));
  expect(container.querySelector('[aria-label="Total de cruces"]')?.textContent).toBe("3");
  expect(container.querySelector("img")?.getAttribute("src")).toContain("eA==");
  await act(async () => socket.message(update(3, 5, 4, "eQ==")));
  expect(container.querySelector('[aria-label="Total de cruces"]')?.textContent).toBe("4");
  expect(container.querySelector("img")?.getAttribute("src")).toContain("eQ==");
});

it("ignora un mensaje anterior al checkpoint consultado por REST", async () => {
  vi.mocked(fetch).mockResolvedValueOnce(response({ ...result, revision: 2 }) as Response);
  await act(async () => root.render(<LiveAnalysisPage jobId="job-1" apiBaseUrl="http://api.test" />));
  await act(async () => Socket.instances[0].message(update(1, 1, 99, "eA==")));
  expect(container.querySelector('img[alt="Cámara en vivo"]')).toBeNull();
  expect(container.querySelector('[aria-label="Total de cruces"]')?.textContent).toBe("0");
});

it("espera el estado terminal para dar por terminado un stop aceptado", async () => {
  await act(async () => root.render(<LiveAnalysisPage jobId="job-1" apiBaseUrl="http://api.test" />));
  await click(byButton(container, "Detener análisis"));
  expect(container.textContent).toContain("Finalizando");
  expect(container.textContent).not.toContain("Análisis finalizado");
  expect(byButton(container, "Detener análisis").disabled).toBe(true);
  await act(async () => Socket.instances[0].message({ type: "job.terminal", job_id: "job-1",
    session_id: "session-1", schema_version: "1", status: "completed" }));
  expect(container.textContent).toContain("Análisis finalizado");
});

it("marca la desconexión sin sumar acumulados ni mostrar un frame como reciente", async () => {
  await act(async () => root.render(<LiveAnalysisPage jobId="job-1" apiBaseUrl="http://api.test" />));
  const socket = Socket.instances[0];
  await act(async () => socket.message(update(1, 1, 2, "eA==")));
  await act(async () => socket.onclose?.());
  expect(container.textContent).toContain("Conexión perdida");
  expect(container.querySelector('[aria-label="Total de cruces"]')?.textContent).toBe("2");
});

function framingCheck() {
  return { type: "live.reconnect-check", schema_version: "3", source_kind: "webcam",
    job_id: "job-1", session_id: "session-1", revision: 2, segment_index: 1,
    capture_status: "awaiting_confirmation", device_index: 0, width: 320, height: 180,
    backend: "fake", image_media_type: "image/jpeg", image_base64: "eQ==",
    check_token: "fresh", expires_in_seconds: 60 };
}

it("requiere confirmar el encuadre neutral sin cambiar los cruces del último frame", async () => {
  await act(async () => root.render(<LiveAnalysisPage jobId="job-1" apiBaseUrl="http://api.test" />));
  const socket = Socket.instances[0];
  await act(async () => socket.message(update(1, 1, 3, "eA==")));
  await act(async () => socket.message(framingCheck()));
  expect(container.querySelector('[aria-label="Total de cruces"]')?.textContent).toBe("3");
  expect(container.querySelector('img[alt="Encuadre para reanudar"]')?.getAttribute("src")).toContain("eQ==");
  expect(byButton(container, "Reanudar análisis").disabled).toBe(true);
  await click(byLabel(container, "Confirmo que el encuadre coincide con la configuración"));
  await click(byButton(container, "Reanudar análisis"));
  const calls = vi.mocked(fetch).mock.calls;
  const confirmation = calls.find(([url]) => String(url).endsWith("/live/confirm-resume"));
  expect(confirmation?.[1]?.body).toBe(JSON.stringify({ check_token: "fresh", frame_confirmed: true }));
  expect(container.querySelector('[aria-label="Total de cruces"]')?.textContent).toBe("3");
  await act(async () => socket.message({ ...update(3, 2, 4, "eg=="), segment_index: 1 }));
  expect(container.querySelector('img[alt="Encuadre para reanudar"]')).toBeNull();
  expect(container.querySelector('[aria-label="Total de cruces"]')?.textContent).toBe("4");
});

it("vence la comprobación y permite pedir otro intento sin reanudar automáticamente", async () => {
  vi.useFakeTimers();
  await act(async () => root.render(<LiveAnalysisPage jobId="job-1" apiBaseUrl="http://api.test" />));
  await act(async () => Socket.instances[0].message(framingCheck()));
  await click(byLabel(container, "Confirmo que el encuadre coincide con la configuración"));
  await act(async () => vi.advanceTimersByTimeAsync(60000));
  expect(byButton(container, "Reanudar análisis").disabled).toBe(true);
  expect(container.textContent).toContain("La comprobación venció");
  await click(byButton(container, "Reintentar cámara"));
  expect(vi.mocked(fetch).mock.calls.some(([url]) => String(url).endsWith("/live/retry"))).toBe(true);
  expect(vi.mocked(fetch).mock.calls.some(([url]) => String(url).endsWith("/live/confirm-resume"))).toBe(false);
});
