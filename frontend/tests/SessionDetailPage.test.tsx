import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SessionDetailPage } from "../src/pages/SessionDetailPage";
import type { SceneVersionSummary } from "../src/types/scene";
import type { SessionDetail, VideoAvailability } from "../src/types/session";
import { byButton, byLabel, chooseFile, click } from "./dom";

const API = "http://api.test";
const camera = { id: "cam-1", name: "Cam 01", created_at: "2026-09-28T00:00:00Z" };

function videoSession(
  availability: VideoAvailability,
  overrides: Partial<SessionDetail> = {},
): SessionDetail {
  return {
    id: "s-1",
    name: "Mañana",
    source_kind: "video_file",
    camera,
    camera_id: "Cam 01",
    created_at: "2026-09-28T10:00:00Z",
    video: {
      relative_path: "s-1.mp4",
      original_filename: "entrada.mp4",
      size_bytes: 1024,
      sha256: "a".repeat(64),
      origin_machine_id: "pc-lab-01",
      width: 1280,
      height: 720,
      fps: 25,
      fps_is_estimated: false,
      frame_count: 50,
      declared_frame_count: null,
      appears_incomplete: false,
      duration_seconds: 2,
      registered_at: "2026-09-28T10:00:00Z",
      availability,
    },
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

function response(status: number, body: unknown) {
  return { ok: status >= 200 && status < 300, status, text: async () => JSON.stringify(body) };
}

interface Reply {
  status: number;
  body: unknown;
}

function sceneVersion(versionNumber: number, overrides: Partial<SceneVersionSummary> = {}) {
  return {
    id: `v-${versionNumber}`,
    camera_id: "cam-1",
    version_number: versionNumber,
    reference_session_id: "s-1",
    frame_width: 1280,
    frame_height: 720,
    created_by_machine_id: "pc-lab-01",
    created_at: `2026-09-2${versionNumber}T10:00:00Z`,
    shop_count: versionNumber,
    ...overrides,
  } satisfies SceneVersionSummary;
}

class FakeXhr {
  static instances: FakeXhr[] = [];
  method = "";
  url = "";
  status = 0;
  responseText = "";
  upload: { onprogress?: () => void; onload?: () => void } = {};
  onload?: () => void;
  onerror?: () => void;
  onabort?: () => void;

  constructor() {
    FakeXhr.instances.push(this);
  }

  open(method: string, url: string) {
    this.method = method;
    this.url = url;
  }

  setRequestHeader() {}

  send() {}

  abort() {
    this.onabort?.();
  }

  respond(status: number, body: unknown) {
    this.status = status;
    this.responseText = JSON.stringify(body);
    this.onload?.();
  }
}

describe("SessionDetailPage", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    FakeXhr.instances = [];
    vi.stubGlobal("XMLHttpRequest", FakeXhr);
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
    vi.unstubAllGlobals();
  });

  let fetchMock: ReturnType<typeof vi.fn>;

  // Responde según la URL: la sesión, las versiones de escena de su cámara y la creación de trabajos.
  async function render(
    session: SessionDetail | Reply,
    { versions = [], job, removal = { status: 204, body: null } }: { versions?: SceneVersionSummary[] | Reply; job?: Reply; removal?: Reply } = {},
  ) {
    const result = "status" in session ? session : { status: 200, body: session };
    const versionsReply = Array.isArray(versions) ? { status: 200, body: versions } : versions;
    fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith("/scene-versions")) return response(versionsReply.status, versionsReply.body);
      if (url.includes("/scene-versions/")) {
        if (init?.method === "DELETE") return response(removal.status, removal.body);
        const version = Array.isArray(versions) ? versions.find((item) => url.endsWith(`/${item.id}`)) : undefined;
        return response(200, { ...version, shops: [{ shop_id: "shop-1", name: `Local de configuración ${version?.version_number}`, zones: { front: [[0.1, 0.5], [0.3, 0.5], [0.3, 0.7], [0.1, 0.7]] }, entry_line: { start: [0.1, 0.6], end: [0.3, 0.6], entry_direction: "a_to_b" } }] });
      }
      if (url.endsWith("/jobs")) {
        return job === undefined ? response(500, {}) : response(job.status, job.body);
      }
      return response(result.status, result.body);
    });
    vi.stubGlobal("fetch", fetchMock);
    await act(async () => root.render(<SessionDetailPage sessionId="s-1" apiBaseUrl={API} />));
  }

  function analysisSection(): HTMLElement {
    const section = container.querySelector<HTMLElement>('section[aria-labelledby="analysis-title"]');
    if (section === null) throw new Error("No se encontró la sección Iniciar análisis.");
    return section;
  }

  async function startAnalysis(): Promise<void> {
    await click(byButton(analysisSection(), "Iniciar análisis de video"));
    await act(async () => {
      await vi.waitFor(() =>
        expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith("/jobs"))).toBe(true),
      );
    });
  }

  function jobRequestBody(): unknown {
    const call = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/jobs"));
    return JSON.parse((call?.[1] as RequestInit).body as string);
  }

  function configurationSelected(number: number): boolean {
    return byLabel<HTMLButtonElement>(container, "Configuración de escena").textContent?.includes(`Configuración ${number}`) ?? false;
  }
  async function chooseConfiguration(number: number) {
    await click(byLabel<HTMLButtonElement>(container, "Configuración de escena"));
    await click(document.querySelector(`[role="option"][aria-label="Configuración ${number}"]`)!);
  }

  function definition(term: string): string | null | undefined {
    const dt = Array.from(container.querySelectorAll("dt")).find((item) => item.textContent === term);
    return dt?.nextElementSibling?.textContent;
  }

  it("abre una lista accesible y confirma una configuración con teclado", async () => {
    await render(videoSession("available"), { versions: [sceneVersion(4), sceneVersion(1)] });
    const control = container.querySelector<HTMLElement>('[role="combobox"]')!;
    expect(control).not.toBeNull();
    await act(async () => control.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true })));
    expect(document.querySelector('[role="listbox"]')).not.toBeNull();
    await act(async () => control.dispatchEvent(new KeyboardEvent("keydown", { key: "End", bubbles: true })));
    await act(async () => control.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true })));
    expect(container.querySelector('[aria-label="Configuración activa"]')?.textContent).toBe("Configuración 1");
    expect(document.querySelector('[role="listbox"]')).toBeNull();
    await act(async () => window.dispatchEvent(new Event("resize")));
    expect(document.querySelector('[role="listbox"]')).toBeNull();
  });

  it("sincroniza selector, badge y resumen sin abrir metadatos", async () => {
    await render(videoSession("available"), { versions: [sceneVersion(4), sceneVersion(1)] });
    expect(configurationSelected(4)).toBe(true);
    await chooseConfiguration(1);
    expect(container.querySelector('[aria-label="Configuración activa"]')?.textContent).toBe("Configuración 1");
    expect(container.textContent).toContain("1 zona de interés");
    expect(container.querySelector<HTMLDetailsElement>('details[aria-label="Detalles del archivo y sesión"]')?.open).toBe(false);
  });

  it("muestra metadatos, frame de referencia y enlace al editor", async () => {
    await render(videoSession("available"));

    expect(container.querySelector("h1")?.textContent).toBe("Mañana");
    expect(container.querySelector("header")).not.toBeNull();
    expect(container.querySelector('svg[role="img"]')).not.toBeNull();
    expect(definition("Resolución")).toBe("1280 × 720");
    expect(definition("FPS")).toBe("25");
    expect(definition("Duración")).toBe("2.00 s");
    expect(definition("Frames")).toBe("50");
    expect(definition("Equipo de origen")).toBe("pc-lab-01");
    expect(container.textContent).not.toContain("SHA-256");
    expect(container.textContent).not.toContain("a".repeat(64));
    expect(definition("Archivo original")).toBe("entrada.mp4");

    expect(container.querySelector("image")?.getAttribute("href")).toBe(`${API}/sessions/s-1/reference-frame`);
    expect(container.querySelector('svg[role="img"]')?.getAttribute("aria-label")).toBe("Frame de referencia de Mañana");
    expect(Array.from(container.querySelectorAll('a[href="/sessions/s-1/editor"]')).some((link) => link.textContent === "Editar en canvas")).toBe(true);
    expect(container.textContent).toContain("Video disponible en este equipo");
    expect(container.textContent).not.toContain("Volver a cargar el video");
  });

  it("avisa si el archivo de video parece incompleto", async () => {
    const session = videoSession("available");
    session.video = {
      ...session.video!,
      frame_count: 45,
      declared_frame_count: 50,
      appears_incomplete: true,
    };
    await render(session);

    const notice = container.querySelector('section[aria-label="Consola de inferencia"] > [role="status"]');
    expect(notice?.textContent).toBe(
      "El archivo parece incompleto: se leyeron 45 de 50 frames declarados.",
    );
  });

  it("no avisa si el video no parece incompleto", async () => {
    const session = videoSession("available");
    session.video = { ...session.video!, declared_frame_count: 50, appears_incomplete: false };
    await render(session);

    expect(container.textContent).not.toContain("parece incompleto");
  });

  it("no avisa cuando no hay cantidad de frames declarada", async () => {
    await render(videoSession("available"));

    expect(container.textContent).not.toContain("parece incompleto");
  });

  it("marca el fps estimado", async () => {
    const session = videoSession("available");
    session.video = { ...session.video!, fps: 29.97, fps_is_estimated: true };
    await render(session);

    expect(definition("FPS")).toBe("29.97 (estimado)");
  });

  it.each([
    ["missing", "Archivo no encontrado en el almacenamiento local.", true],
    ["mismatch", "El archivo de este equipo no coincide con el video registrado", true],
    ["not_configured", "Este equipo no tiene configurada la carpeta de videos", false],
  ] as const)("informa la disponibilidad %s", async (availability, text, canRelink) => {
    await render(videoSession(availability));

    expect(container.querySelector("[data-availability]")?.textContent).toContain(text);
    expect(container.textContent?.includes("Re-vincular video")).toBe(canRelink);
    expect(container.querySelector('svg[role="img"]')).not.toBeNull();
  });

  it("avisa los duplicados con enlaces", async () => {
    await render(videoSession("available", { duplicate_session_ids: ["s-0"] }));

    expect(container.querySelector('a[href="/sessions/s-0"]')?.textContent).toBe("Sesión s-0");
  });

  it("vuelve a cargar el video y muestra hash_mismatch tal cual", async () => {
    await render(videoSession("missing"));
    const input = container.querySelector<HTMLInputElement>('input[type="file"]')!;
    await chooseFile(input, new File(["x"], "otro.mp4"));
    await act(async () => {
      await vi.waitFor(() => expect(FakeXhr.instances).toHaveLength(1));
    });

    const request = FakeXhr.instances[0]!;
    expect(request.method).toBe("PUT");
    expect(request.url).toBe(`${API}/sessions/s-1/video`);
    await act(async () =>
      request.respond(409, {
        detail: {
          code: "hash_mismatch",
          message: "El archivo no es el que se registró. Elegí el mismo archivo que se registró originalmente.",
        },
      }),
    );
    expect(container.querySelector('[role="alert"]')?.textContent).toBe(
      "El archivo no es el que se registró. Elegí el mismo archivo que se registró originalmente.",
    );

    await chooseFile(input, new File(["x"], "entrada.mp4"));
    await act(async () => {
      await vi.waitFor(() => expect(FakeXhr.instances).toHaveLength(2));
    });
    await act(async () => FakeXhr.instances[1]!.respond(200, videoSession("available")));

    expect(container.textContent).toContain("Video disponible en este equipo");
    expect(container.textContent).toContain("El video se volvió a cargar en este equipo.");
    expect(container.textContent).not.toContain("Volver a cargar el video");
  });

  it("muestra una sesión sintética sin video ni editor", async () => {
    await render(
      videoSession("available", {
        source_kind: "synthetic",
        video: null,
        reference_frame: null,
      }),
    );

    expect(definition("Tipo")).toBe("Sintética");
    expect(container.textContent).toContain("no tiene video ni frame de referencia");
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector('a[href="/sessions/s-1/editor"]')).toBeNull();
    expect(container.textContent).not.toContain("Iniciar análisis");
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("scene-versions"))).toBe(false);
  });

  describe("Iniciar análisis", () => {
    it("muestra en el frame las zonas de la configuración elegida", async () => {
      await render(videoSession("available"), { versions: [sceneVersion(2), sceneVersion(1)] });
      const canvas = container.querySelector('svg[role="img"]')!;
      expect(canvas.textContent).toContain("Local de configuración 2");
      await chooseConfiguration(1);
      expect(canvas.textContent).toContain("Local de configuración 1");
      expect(canvas.textContent).not.toContain("Local de configuración 2");
      const firstPoint = canvas.querySelector("polygon")?.getAttribute("points")?.split(" ")[0];
      expect(firstPoint).toBe("128,360");
    });

    it("elimina la configuración seleccionada y muestra la siguiente disponible", async () => {
      await render(videoSession("available"), { versions: [sceneVersion(2), sceneVersion(1)] });
      await click(analysisSection().querySelector<HTMLButtonElement>('[aria-label="Eliminar configuración 2"]')!);
      await click(byButton(container.querySelector("dialog")!, "Eliminar configuración"));
      expect(fetchMock).toHaveBeenCalledWith(`${API}/scene-versions/v-2`, { method: "DELETE" });
      expect(configurationSelected(1)).toBe(true);
      expect(analysisSection().querySelector('option[value="v-2"]')).toBeNull();
      expect(container.querySelector('svg[role="img"]')?.textContent).toContain("Local de configuración 1");
    });

    it("conserva la configuración si la API bloquea su eliminación", async () => {
      await render(videoSession("available"), { versions: [sceneVersion(2)], removal: { status: 409, body: { detail: { code: "scene_version_has_active_jobs", message: "El análisis sigue activo." } } } });
      await click(analysisSection().querySelector<HTMLButtonElement>('[aria-label="Eliminar configuración 2"]')!);
      await click(byButton(container.querySelector("dialog")!, "Eliminar configuración"));
      expect(configurationSelected(2)).toBe(true);
      expect(container.querySelector('dialog [role="alert"]')?.textContent).toBe("El análisis sigue activo.");
    });

    it("pide las versiones de la cámara y preselecciona la última", async () => {
      await render(videoSession("available"), {
        versions: [sceneVersion(2), sceneVersion(3), sceneVersion(1)],
      });

      expect(fetchMock).toHaveBeenCalledWith(`${API}/cameras/cam-1/scene-versions`, undefined);
      expect(configurationSelected(3)).toBe(true);
      expect(configurationSelected(2)).toBe(false);
      expect(configurationSelected(1)).toBe(false);
      expect(byButton(analysisSection(), "Iniciar análisis de video").disabled).toBe(false);
    });

    it("crea el trabajo con la configuración anterior elegida y enlaza a su avance", async () => {
      await render(videoSession("available"), {
        versions: [sceneVersion(2), sceneVersion(1)],
        job: {
          status: 201,
          body: {
            id: "job-9",
            session_id: "s-1",
            kind: "video_analysis",
            scene_version_id: "v-1",
            status: "pending",
            created_at: "2026-09-28T11:00:00Z",
          },
        },
      });

      await chooseConfiguration(1);
      await startAnalysis();

      expect(jobRequestBody()).toEqual({ kind: "video_analysis", scene_version_id: "v-1" });
      const status = analysisSection().querySelector('[role="status"]');
      expect(status?.querySelector("a")?.getAttribute("href")).toBe("/?job=job-9");
      expect(status?.textContent).toContain("configuración 1");
    });

    it("sin versiones avisa y enlaza al editor sin ofrecer el botón", async () => {
      await render(videoSession("available"), { versions: [] });

      const section = analysisSection();
      expect(section.textContent).toContain("no tiene ninguna configuración de escena");
      expect(section.querySelector('a[href="/sessions/s-1/editor"]')).not.toBeNull();
      expect(section.querySelector("select")).toBeNull();
      expect(section.querySelector("button")).toBeNull();
    });

    it("informa scene_not_configured con enlace al editor", async () => {
      await render(videoSession("available"), {
        versions: [sceneVersion(1)],
        job: {
          status: 409,
          body: {
            detail: {
              code: "scene_not_configured",
              message: "La cámara no tiene ninguna configuración de escena.",
            },
          },
        },
      });

      await startAnalysis();

      const alert = analysisSection().querySelector('[role="alert"]');
      expect(alert?.textContent).toContain("La cámara no tiene ninguna configuración de escena.");
      expect(alert?.querySelector('a[href="/sessions/s-1/editor"]')).not.toBeNull();
    });

    it("informa aspect_ratio_mismatch con los ratios y enlaza al editor", async () => {
      await render(videoSession("available"), {
        versions: [sceneVersion(1, { frame_width: 640, frame_height: 480 })],
        job: {
          status: 409,
          body: {
            detail: {
              code: "aspect_ratio_mismatch",
              message: "La relación de aspecto difiere.",
              video_aspect_ratio: 1.777778,
              version_aspect_ratio: 1.333333,
            },
          },
        },
      });

      await startAnalysis();

      const alert = analysisSection().querySelector('[role="alert"]');
      expect(alert?.textContent).toContain("1.778");
      expect(alert?.textContent).toContain("1.333");
      expect(alert?.querySelector('a[href="/sessions/s-1/editor"]')).not.toBeNull();
    });

    it("muestra el message del backend ante otros errores", async () => {
      await render(videoSession("available"), {
        versions: [sceneVersion(1)],
        job: {
          status: 422,
          body: {
            detail: {
              code: "scene_version_other_camera",
              message: "La versión de escena elegida no existe o es de otra cámara.",
            },
          },
        },
      });

      await startAnalysis();

      const alert = analysisSection().querySelector('[role="alert"]');
      expect(alert?.textContent).toBe("La versión de escena elegida no existe o es de otra cámara.");
      expect(alert?.querySelector("a")).toBeNull();
    });

    it("informa si no se pudieron cargar las versiones", async () => {
      await render(videoSession("available"), {
        versions: { status: 404, body: { detail: { code: "not_found", message: "Cámara inexistente." } } },
      });

      expect(analysisSection().querySelector('[role="alert"]')?.textContent).toBe("Cámara inexistente.");
      expect(analysisSection().querySelector("button")).toBeNull();
    });
  });

  it("informa una sesión inexistente", async () => {
    await render({ status: 404, body: { detail: { code: "not_found", message: "No existe" } } });

    expect(container.querySelector('[role="alert"]')?.textContent).toBe("Sesión inexistente.");
  });
});
