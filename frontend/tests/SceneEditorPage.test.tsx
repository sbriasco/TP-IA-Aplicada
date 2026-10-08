/**
 * Pruebas de `SceneEditorPage` (specs/004, T044): carga de sesión, frame y última versión,
 * guardado (éxito y 422) y advertencia de salida con cambios sin guardar (FR-030, FR-034, FR-035).
 */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SceneEditorPage } from "../src/pages/SceneEditorPage";
import type { ProcessedSession } from "../src/api/processedSessions";
import type { SceneIssue, SceneVersion, SceneVersionSummary } from "../src/types/scene";
import type { SessionDetail } from "../src/types/session";
import { byButton, byLabel, changeValue, click } from "./dom";

const API = "http://api.test";
const camera = { id: "cam-1", name: "Cam 01", created_at: "2026-09-28T00:00:00Z" };

function session(overrides: Partial<SessionDetail> = {}): SessionDetail {
  return {
    id: "s-1",
    name: "Mañana",
    source_kind: "video_file",
    camera,
    camera_id: "Cam 01",
    created_at: "2026-09-28T10:00:00Z",
    video: null,
    reference_frame: {
      frame_index: 0,
      video_timestamp_seconds: 0,
      width: 1280,
      height: 720,
      url: "/sessions/s-1/reference-frame",
    },
    duplicate_session_ids: [],
    ...overrides,
  };
}

function summary(versionNumber: number, overrides: Partial<SceneVersionSummary> = {}): SceneVersionSummary {
  return {
    id: `v-${versionNumber}`,
    camera_id: "cam-1",
    version_number: versionNumber,
    reference_session_id: "s-0",
    frame_width: 1280,
    frame_height: 720,
    created_by_machine_id: null,
    created_at: `2026-09-2${versionNumber}T10:00:00Z`,
    shop_count: 1,
    ...overrides,
  };
}

function fullVersion(versionNumber: number, overrides: Partial<SceneVersion> = {}): SceneVersion {
  return {
    ...summary(versionNumber),
    shops: [
      {
        shop_id: "shop-a",
        name: "Local A",
        zones: {
          front: [
            [0.125, 0.5],
            [0.375, 0.5],
            [0.375, 0.75],
            [0.125, 0.75],
          ],
        },
        entry_line: { start: [0.125, 0.875], end: [0.375, 0.875], entry_direction: "a_to_b" },
      },
    ],
    ...overrides,
  };
}

function response(status: number, body: unknown) {
  return { ok: status >= 200 && status < 300, status, text: async () => JSON.stringify(body) };
}

interface Reply {
  status: number;
  body: unknown;
}

describe("SceneEditorPage", () => {
  let container: HTMLDivElement;
  let root: Root;
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    window.history.replaceState(null, "", "/sessions/s-1/editor");
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    window.history.replaceState(null, "", "/");
  });

  async function render({
    detail = session(),
    versions = [],
    version,
    save,
    jobs = [],
    jobsReply,
  }: {
    detail?: SessionDetail;
    versions?: SceneVersionSummary[];
    version?: SceneVersion;
    save?: Reply;
    jobs?: ProcessedSession[];
    jobsReply?: Reply;
  } = {}) {
    fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url === `${API}/processed-sessions`) return response(jobsReply?.status ?? 200, jobsReply?.body ?? jobs);
      if (url === `${API}/sessions/s-1`) return response(200, detail);
      if (url === `${API}/cameras/cam-1/scene-versions`) {
        if (init?.method === "POST") {
          return save === undefined ? response(500, {}) : response(save.status, save.body);
        }
        return response(200, versions);
      }
      if (version !== undefined && url === `${API}/scene-versions/${version.id}`) {
        return response(200, version);
      }
      return response(404, { detail: { code: "not_found", message: "No existe." } });
    });
    vi.stubGlobal("fetch", fetchMock);
    await act(async () => root.render(<SceneEditorPage sessionId="s-1" apiBaseUrl={API} />));
    await act(async () => {
      await vi.waitFor(() => expect(container.querySelector('[data-loading="true"]')).toBeNull());
    });
  }

  function vertices(): NodeListOf<SVGCircleElement> {
    return container.querySelectorAll<SVGCircleElement>('circle[role="button"]');
  }

  it("respeta las etiquetas Entrada/Salida de webcam al editar e invertir la línea", async () => {
    await render({ detail: session({ source_kind: "webcam", live_source: {
      machine_id: "local", device_index: 0, capture_backend: "fake", width: 1280, height: 720,
      reported_fps: 30, label_mode: "access", prepared_at: camera.created_at, frame_checked_at: null,
    } }), versions: [summary(1)], version: fullVersion(1) });
    const sideA = container.querySelector('[aria-label="Lado de salida de Local A"]');
    const sideB = container.querySelector('[aria-label="Lado de entrada de Local A"]');
    expect(sideA?.textContent).toBe("Salida");
    expect(sideB?.textContent).toBe("Entrada");
    await click(byButton(container, "Línea de entrada"));
    await click(byButton(container, "Invertir entrada y salida"));
    expect(sideA?.textContent).toBe("Entrada");
    expect(sideB?.textContent).toBe("Salida");
  });

  function job(overrides: Partial<ProcessedSession> = {}): ProcessedSession {
    return { session_id: "s-1", name: "Mañana", video_filename: "video.mp4",
      video_availability: "available", job_id: "job-1", status: "completed",
      finished_at: "2026-10-06T10:00:00Z", failure_code: null, failure_message: null,
      scene_version_id: "v-1", version_number: 1, result_complete: true, ...overrides };
  }

  it.each([
    { name: "video con resultados", jobs: [job()], source: "video_file" as const, href: "/sessions/s-1/results" },
    { name: "video sin análisis", jobs: [], source: "video_file" as const, href: "/sessions/s-1" },
    { name: "video incompleto", jobs: [job({ result_complete: false })], source: "video_file" as const, href: "/sessions/s-1" },
    { name: "video procesándose", jobs: [job({ status: "processing", result_complete: false })], source: "video_file" as const, href: "/sessions/s-1" },
    { name: "resultados de otra sesión", jobs: [job({ session_id: "s-2" })], source: "video_file" as const, href: "/sessions/s-1" },
    { name: "webcam finalizada", jobs: [job({ source_kind: "webcam" })], source: "webcam" as const, href: "/live/jobs/job-1/results" },
    { name: "webcam sin análisis", jobs: [], source: "webcam" as const, href: "/sessions/s-1/live" },
  ])("continúa al destino correcto: $name", async ({ jobs, source, href }) => {
    await render({ detail: session({ source_kind: source }), versions: [summary(1)], version: fullVersion(1), jobs });
    const link = Array.from(container.querySelectorAll("a")).find(element => element.textContent?.includes("Continuar a resultados"));
    expect(link?.getAttribute("href")).toBe(href);
    await followLink(link!);
    expect(window.location.pathname).toBe(href);
  });

  it("permite reintentar la consulta de resultados sin bloquear el editor", async () => {
    const reply: Reply = { status: 503, body: { detail: { code: "unavailable", message: "No disponible." } } };
    await render({ versions: [summary(1)], version: fullVersion(1), jobsReply: reply });
    expect(byButton(container, "Continuar a resultados").disabled).toBe(true);
    expect(vertices()).toHaveLength(6);
    reply.status = 200;
    reply.body = [job()];
    await click(byButton(container, "Reintentar"));
    await act(async () => { await vi.waitFor(() => expect(container.querySelector('a[href="/sessions/s-1/results"]')).not.toBeNull()); });
    expect(container.querySelector('[role="alert"]')).toBeNull();
    await click(byButton(container, "Agregar zona"));
    expect(byButton(container, "Continuar a resultados").disabled).toBe(true);
  });

  function saveRequestBody(): Record<string, unknown> {
    const call = fetchMock.mock.calls.find(([, init]) => (init as RequestInit | undefined)?.method === "POST");
    return JSON.parse((call?.[1] as RequestInit).body as string) as Record<string, unknown>;
  }

  it("no guarda si no hay cambios, incluso al editar y restaurar el nombre", async () => {
    await render({ versions: [summary(2)], version: fullVersion(2) });
    const button = byButton(container, "Guardar configuración");
    expect(button.disabled).toBe(true);
    await click(byButton(container, "Local A"));
    await changeValue(byLabel<HTMLInputElement>(container, "Nombre de la zona"), "Modificado");
    expect(button.disabled).toBe(false);
    await changeValue(byLabel<HTMLInputElement>(container, "Nombre de la zona"), "Local A");
    expect(button.disabled).toBe(true);
    await changeValue(byLabel<HTMLInputElement>(container, "Título de la configuración"), "Otro título local");
    expect(button.disabled).toBe(true);
    await click(button);
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
    expect(unloadPrevented()).toBe(false);
  });

  /** Clic cancelable, como el de un navegador: `Link` lo cancela y navega con `navigate`. */
  async function followLink(link: HTMLAnchorElement) {
    await act(async () => {
      link.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, button: 0 }));
    });
  }

  function unloadPrevented(): boolean {
    const event = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(event);
    return event.defaultPrevented;
  }

  async function save() {
    await click(byButton(container, "Guardar configuración"));
    await act(async () => {
      await vi.waitFor(() =>
        expect(
          fetchMock.mock.calls.some(([, init]) => (init as RequestInit | undefined)?.method === "POST"),
        ).toBe(true),
      );
    });
    await act(async () => {
      await vi.waitFor(() => expect(Array.from(container.querySelectorAll("button")).some(button => button.textContent === "Guardando…")).toBe(false));
    });
  }

  it("precarga la última versión de la cámara sobre el frame de la sesión", async () => {
    await render({ versions: [summary(1), summary(2)], version: fullVersion(2) });

    expect(fetchMock.mock.calls.map(([url]) => url)).toContain(`${API}/scene-versions/v-2`);
    expect(container.querySelector("h1")?.textContent).toBe("Mañana");
    expect(container.querySelector("header")?.textContent).not.toContain("Editor");
    expect(container.querySelector("image")?.getAttribute("href")).toBe(
      `${API}/sessions/s-1/reference-frame`,
    );
    expect(vertices()).toHaveLength(6);
    expect(container.querySelector('[aria-label="Vértice 1 de área externa de Local A"]')).not.toBeNull();
    expect(container.textContent).toContain("Editando la configuración 2.");
    expect(container.querySelector('[role="alert"]')).toBeNull();
    expect(Array.from(container.querySelectorAll('a[href="/sessions/s-1"]')).some((link) => link.textContent === "Volver a la sesión")).toBe(true);
  });

  it("edita nombres y oculta capas sin quitarlas del guardado", async () => {
    await render({ versions: [summary(2)], version: fullVersion(2), save: { status: 201, body: { ...fullVersion(3), warnings: [] } } });
    await click(byButton(container, "Local A"));
    await changeValue(byLabel<HTMLInputElement>(container, "Nombre de la zona"), "Entrada");
    expect(byLabel<HTMLInputElement>(container, "Nombre de la zona").value).toBe("Entrada");
    await click(container.querySelector('[aria-label="Ocultar Área externa de Entrada"]')!);
    expect(container.querySelector('polygon[data-role="front"]')).toBeNull();
    await save();
    expect(saveRequestBody().shops).toEqual([{ shop_id: "shop-a", name: "Entrada", zones: fullVersion(2).shops[0]!.zones, entry_line: fullVersion(2).shops[0]!.entry_line }]);
  });

  it("sin versiones abre un editor vacío", async () => {
    await render();

    expect(container.querySelector("svg")).not.toBeNull();
    expect(vertices()).toHaveLength(0);
    expect(container.textContent).toContain("Agregá una zona de análisis");
    expect(byButton(container, "Agregar zona")).toBeDefined();
  });

  it("sin frame de referencia muestra un mensaje y no abre el editor", async () => {
    await render({ detail: session({ reference_frame: null }) });

    expect(container.textContent).toContain("Esta sesión no tiene frame de referencia");
    expect(container.querySelector('svg[aria-label="Frame de referencia con la escena"]')).toBeNull();
    expect(fetchMock.mock.calls.map(([url]) => url)).not.toContain(`${API}/cameras/cam-1/scene-versions`);
    expect(container.querySelector('a[href="/sessions/s-1"]')).not.toBeNull();
  });

  it("informa si la sesión no existe", async () => {
    fetchMock = vi.fn(async () => response(404, { detail: { code: "not_found", message: "No existe." } }));
    vi.stubGlobal("fetch", fetchMock);
    await act(async () => root.render(<SceneEditorPage sessionId="s-1" apiBaseUrl={API} />));
    await act(async () => {
      await vi.waitFor(() => expect(container.querySelector('[role="alert"]')).not.toBeNull());
    });

    expect(container.querySelector('[role="alert"]')?.textContent).toBe("Sesión inexistente.");
  });

  it("advierte de forma persistente si la versión tiene otra relación de aspecto", async () => {
    const other = { frame_width: 1920, frame_height: 1440 };
    await render({ versions: [summary(2, other)], version: fullVersion(2, other) });

    const alert = container.querySelector('[role="alert"]');
    expect(alert?.textContent).toContain("pueden verse deformadas");
    expect(vertices()).toHaveLength(6);

    // Sigue visible al editar: solo desaparece al guardar sobre este frame.
    await click(byButton(container, "Local A"));
    await changeValue(byLabel<HTMLInputElement>(container, "Nombre de la zona"), "Local A2");
    expect(container.querySelector('[role="alert"]')?.textContent).toContain("pueden verse deformadas");
  });

  it("guarda una versión nueva y muestra el número y las advertencias", async () => {
    const warning: SceneIssue = {
      rule: "line_not_touching_zones",
      element: "entry_line",
      shop_index: 0,
      shop_name: "Local A",
      message: "La línea de entrada no toca el área externa ni la interior.",
    };
    await render({
      versions: [summary(2)],
      version: fullVersion(2),
      save: { status: 201, body: { ...fullVersion(3, { reference_session_id: "s-1" }), warnings: [warning] } },
    });
    await click(byButton(container, "Local A"));
    await changeValue(byLabel<HTMLInputElement>(container, "Nombre de la zona"), "Local A2");

    await save();

    const body = saveRequestBody();
    expect(body.reference_session_id).toBe("s-1");
    expect(body.base_version_id).toBe("v-2");
    expect(body.shops).toEqual([
      {
        shop_id: "shop-a",
        name: "Local A2",
        zones: fullVersion(2).shops[0].zones,
        entry_line: fullVersion(2).shops[0].entry_line,
      },
    ]);
    expect(container.querySelector('[role="status"]')?.textContent).toBe("Se guardó la configuración 3.");
    expect(container.textContent).toContain(warning.message);
    expect(unloadPrevented()).toBe(false);
    expect(byButton(container, "Guardar configuración").disabled).toBe(true);
  });

  it("ante un 422 marca el elemento y conserva el dibujo", async () => {
    const error: SceneIssue = {
      rule: "self_intersection",
      element: "zone:front",
      shop_index: 0,
      shop_name: "Local A",
      message: "El área externa se cruza a sí misma.",
    };
    await render({
      versions: [summary(2)],
      version: fullVersion(2),
      save: {
        status: 422,
        body: {
          detail: {
            code: "invalid_scene_configuration",
            message: "La configuración tiene errores.",
            errors: [error],
          },
        },
      },
    });
    await click(byButton(container, "Local A"));
    await changeValue(byLabel<HTMLInputElement>(container, "Nombre de la zona"), "Local A2");

    await save();

    const zone = container.querySelector('g[role="group"][aria-label="Área externa de Local A2"]');
    expect(zone?.getAttribute("aria-invalid")).toBe("true");
    expect(zone?.textContent).toContain(error.message);
    expect(vertices()).toHaveLength(6);
    expect(byLabel<HTMLInputElement>(container, "Nombre de la zona").value).toBe("Local A2");
    expect(container.querySelector('[role="alert"]')?.textContent).toContain("No se guardó la configuración");
    expect(unloadPrevented()).toBe(true);
  });

  it("muestra otros errores del guardado sin perder el dibujo", async () => {
    await render({
      versions: [summary(2)],
      version: fullVersion(2),
      save: { status: 409, body: { detail: { code: "conflict", message: "La cámara cambió." } } },
    });

    await click(byButton(container, "Local A"));
    await changeValue(byLabel<HTMLInputElement>(container, "Nombre de la zona"), "Local A2");
    await save();

    expect(container.querySelector('[role="alert"]')?.textContent).toBe("La cámara cambió.");
    expect(vertices()).toHaveLength(6);
  });

  it("registra beforeunload solo mientras hay cambios sin guardar", async () => {
    await render();
    expect(unloadPrevented()).toBe(false);

    await click(byButton(container, "Agregar zona"));
    expect(unloadPrevented()).toBe(true);

    await click(container.querySelector<HTMLButtonElement>('[aria-label="Eliminar zona Zona 1"]')!);
    // Agregar y quitar la misma zona restaura la configuración vacía original.
    expect(unloadPrevented()).toBe(false);
  });

  it("pide confirmación al navegar dentro de la app con cambios sin guardar", async () => {
    await render();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const back = container.querySelector('a[href="/sessions/s-1"]') as HTMLAnchorElement;

    // Sin cambios no pregunta.
    await followLink(back);
    expect(confirm).not.toHaveBeenCalled();
    expect(window.location.pathname).toBe("/sessions/s-1");
    window.history.replaceState(null, "", "/sessions/s-1/editor");

    await click(byButton(container, "Agregar zona"));
    await followLink(back);
    expect(confirm).toHaveBeenCalledTimes(1);
    expect(window.location.pathname).toBe("/sessions/s-1/editor");

    confirm.mockReturnValue(true);
    await followLink(back);
    expect(confirm).toHaveBeenCalledTimes(2);
    expect(window.location.pathname).toBe("/sessions/s-1");
  });

  it("deja de advertir al desmontarse", async () => {
    await render();
    await click(byButton(container, "Agregar zona"));
    expect(unloadPrevented()).toBe(true);

    await act(async () => root.unmount());
    expect(unloadPrevented()).toBe(false);
    root = createRoot(container);
  });
});
