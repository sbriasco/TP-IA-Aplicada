/**
 * Pruebas de `SceneEditorPage` (specs/004, T044): carga de sesión, frame y última versión,
 * guardado (éxito y 422) y advertencia de salida con cambios sin guardar (FR-030, FR-034, FR-035).
 */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SceneEditorPage } from "../src/pages/SceneEditorPage";
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
  }: {
    detail?: SessionDetail;
    versions?: SceneVersionSummary[];
    version?: SceneVersion;
    save?: Reply;
  } = {}) {
    fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
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

  function saveRequestBody(): Record<string, unknown> {
    const call = fetchMock.mock.calls.find(([, init]) => (init as RequestInit | undefined)?.method === "POST");
    return JSON.parse((call?.[1] as RequestInit).body as string) as Record<string, unknown>;
  }

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
    await click(byButton(container, "Guardar versión"));
    await act(async () => {
      await vi.waitFor(() =>
        expect(
          fetchMock.mock.calls.some(([, init]) => (init as RequestInit | undefined)?.method === "POST"),
        ).toBe(true),
      );
    });
    await act(async () => {
      await vi.waitFor(() => expect(byButton(container, "Guardar versión").disabled).toBe(false));
    });
  }

  it("precarga la última versión de la cámara sobre el frame de la sesión", async () => {
    await render({ versions: [summary(1), summary(2)], version: fullVersion(2) });

    expect(fetchMock.mock.calls.map(([url]) => url)).toContain(`${API}/scene-versions/v-2`);
    expect(container.querySelector("h1")?.textContent).toBe("Mañana");
    expect(container.querySelector("header")?.textContent).toContain("Editor");
    expect(container.querySelector("image")?.getAttribute("href")).toBe(
      `${API}/sessions/s-1/reference-frame`,
    );
    expect(vertices()).toHaveLength(6);
    expect(container.querySelector('[aria-label="Vértice 1 de zona frontal de Local A"]')).not.toBeNull();
    expect(container.textContent).toContain("Editando a partir de la versión 2.");
    expect(container.querySelector('[role="alert"]')).toBeNull();
    expect(container.querySelector('a[href="/sessions/s-1"]')?.textContent).toBe("Volver a la sesión");
  });

  it("sin versiones abre un editor vacío", async () => {
    await render();

    expect(container.querySelector("svg")).not.toBeNull();
    expect(vertices()).toHaveLength(0);
    expect(container.textContent).toContain("La cámara Cam 01 todavía no tiene versiones");
    expect(byButton(container, "Agregar local")).toBeDefined();
  });

  it("sin frame de referencia muestra un mensaje y no abre el editor", async () => {
    await render({ detail: session({ reference_frame: null }) });

    expect(container.textContent).toContain("Esta sesión no tiene frame de referencia");
    expect(container.querySelector("svg")).toBeNull();
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
    await changeValue(byLabel<HTMLSelectElement>(container, "Local en edición"), "0");
    await changeValue(byLabel<HTMLInputElement>(container, "Nombre del local"), "Local A2");
    expect(container.querySelector('[role="alert"]')?.textContent).toContain("pueden verse deformadas");
  });

  it("guarda una versión nueva y muestra el número y las advertencias", async () => {
    const warning: SceneIssue = {
      rule: "line_not_touching_zones",
      element: "entry_line",
      shop_index: 0,
      shop_name: "Local A",
      message: "La línea de entrada no toca la zona frontal ni la interior.",
    };
    await render({
      versions: [summary(2)],
      version: fullVersion(2),
      save: { status: 201, body: { ...fullVersion(3, { reference_session_id: "s-1" }), warnings: [warning] } },
    });
    await changeValue(byLabel<HTMLSelectElement>(container, "Local en edición"), "0");
    await changeValue(byLabel<HTMLInputElement>(container, "Nombre del local"), "Local A2");

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
    expect(container.querySelector('[role="status"]')?.textContent).toBe("Se guardó la versión 3.");
    expect(container.textContent).toContain(warning.message);
    expect(unloadPrevented()).toBe(false);
  });

  it("ante un 422 marca el elemento y conserva el dibujo", async () => {
    const error: SceneIssue = {
      rule: "self_intersection",
      element: "zone:front",
      shop_index: 0,
      shop_name: "Local A",
      message: "La zona frontal se cruza a sí misma.",
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
    await changeValue(byLabel<HTMLSelectElement>(container, "Local en edición"), "0");
    await changeValue(byLabel<HTMLInputElement>(container, "Nombre del local"), "Local A2");

    await save();

    const zone = container.querySelector('g[role="group"][aria-label="Zona frontal de Local A2"]');
    expect(zone?.getAttribute("aria-invalid")).toBe("true");
    expect(zone?.textContent).toContain(error.message);
    expect(vertices()).toHaveLength(6);
    expect(byLabel<HTMLInputElement>(container, "Nombre del local").value).toBe("Local A2");
    expect(container.querySelector('[role="alert"]')?.textContent).toContain("No se guardó la versión");
    expect(unloadPrevented()).toBe(true);
  });

  it("muestra otros errores del guardado sin perder el dibujo", async () => {
    await render({
      versions: [summary(2)],
      version: fullVersion(2),
      save: { status: 409, body: { detail: { code: "conflict", message: "La cámara cambió." } } },
    });

    await save();

    expect(container.querySelector('[role="alert"]')?.textContent).toBe("La cámara cambió.");
    expect(vertices()).toHaveLength(6);
  });

  it("registra beforeunload solo mientras hay cambios sin guardar", async () => {
    await render();
    expect(unloadPrevented()).toBe(false);

    await click(byButton(container, "Agregar local"));
    expect(unloadPrevented()).toBe(true);

    await click(byButton(container, "Quitar local de esta versión"));
    // Quitar también es un cambio: sigue sucio hasta guardar.
    expect(unloadPrevented()).toBe(true);
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

    await click(byButton(container, "Agregar local"));
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
    await click(byButton(container, "Agregar local"));
    expect(unloadPrevented()).toBe(true);

    await act(async () => root.unmount());
    expect(unloadPrevented()).toBe(false);
    root = createRoot(container);
  });
});
