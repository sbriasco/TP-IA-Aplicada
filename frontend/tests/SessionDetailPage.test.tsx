import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SessionDetailPage } from "../src/pages/SessionDetailPage";
import type { SessionDetail, VideoAvailability } from "../src/types/session";
import { byLabel, chooseFile, submit } from "./dom";

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

  async function render(session: SessionDetail | { status: number; body: unknown }) {
    const result = "status" in session ? session : { status: 200, body: session };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(result.status, result.body)));
    await act(async () => root.render(<SessionDetailPage sessionId="s-1" apiBaseUrl={API} />));
  }

  function definition(term: string): string | null | undefined {
    const dt = Array.from(container.querySelectorAll("dt")).find((item) => item.textContent === term);
    return dt?.nextElementSibling?.textContent;
  }

  it("muestra metadatos, frame de referencia y enlace al editor", async () => {
    await render(videoSession("available"));

    expect(container.querySelector("h1")?.textContent).toBe("Mañana");
    expect(definition("Resolución")).toBe("1280 × 720");
    expect(definition("FPS")).toBe("25");
    expect(definition("Duración")).toBe("2.00 s");
    expect(definition("Frames")).toBe("50");
    expect(definition("Equipo de origen")).toBe("pc-lab-01");
    expect(definition("SHA-256")).toBe("a".repeat(64));
    expect(definition("Archivo original")).toBe("entrada.mp4");

    const image = container.querySelector("img") as HTMLImageElement;
    expect(image.src).toBe(`${API}/sessions/s-1/reference-frame`);
    expect(image.alt).toBe("Frame de referencia de Mañana");
    expect(container.querySelector('a[href="/sessions/s-1/editor"]')?.textContent).toBe(
      "Editar escena",
    );
    expect(container.textContent).toContain("Video disponible en este equipo");
    expect(container.textContent).not.toContain("Volver a cargar el video");
  });

  it("marca el fps estimado", async () => {
    const session = videoSession("available");
    session.video = { ...session.video!, fps: 29.97, fps_is_estimated: true };
    await render(session);

    expect(definition("FPS")).toBe("29.97 (estimado)");
  });

  it.each([
    ["missing", "Video no disponible en este equipo", true],
    ["mismatch", "El archivo de este equipo no coincide con el video registrado", true],
    ["not_configured", "Este equipo no tiene configurada la carpeta de videos", false],
  ] as const)("informa la disponibilidad %s", async (availability, text, canRelink) => {
    await render(videoSession(availability));

    expect(container.querySelector("[data-availability]")?.textContent).toContain(text);
    expect(container.textContent?.includes("Volver a cargar el video")).toBe(canRelink);
    expect(container.querySelector("img")).not.toBeNull();
  });

  it("avisa los duplicados con enlaces", async () => {
    await render(videoSession("available", { duplicate_session_ids: ["s-0"] }));

    expect(container.querySelector('a[href="/sessions/s-0"]')?.textContent).toBe("Sesión s-0");
  });

  it("vuelve a cargar el video y muestra hash_mismatch tal cual", async () => {
    await render(videoSession("missing"));
    const form = container.querySelector("section form") as HTMLFormElement;
    await chooseFile(byLabel<HTMLInputElement>(form, "Archivo de video"), new File(["x"], "otro.mp4"));
    await submit(form);
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

    await submit(form);
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
  });

  it("informa una sesión inexistente", async () => {
    await render({ status: 404, body: { detail: { code: "not_found", message: "No existe" } } });

    expect(container.querySelector('[role="alert"]')?.textContent).toBe("Sesión inexistente.");
  });
});
