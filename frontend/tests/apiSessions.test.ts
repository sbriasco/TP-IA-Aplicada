import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiRequestError } from "../src/api/http";
import {
  getSession,
  listSessions,
  referenceFrameUrl,
  registerVideoSession,
  relinkVideo,
} from "../src/api/sessions";

const API = "http://api.test";

class FakeXhr {
  static last: FakeXhr;
  method = "";
  url = "";
  headers: Record<string, string> = {};
  body: unknown;
  status = 0;
  responseText = "";
  aborted = false;
  upload: {
    onprogress?: (event: { lengthComputable: boolean; loaded: number; total: number }) => void;
    onload?: () => void;
  } = {};
  onload?: () => void;
  onerror?: () => void;
  onabort?: () => void;

  constructor() {
    FakeXhr.last = this;
  }

  open(method: string, url: string) {
    this.method = method;
    this.url = url;
  }

  setRequestHeader(name: string, value: string) {
    this.headers[name] = value;
  }

  send(body: unknown) {
    this.body = body;
  }

  abort() {
    this.aborted = true;
    this.onabort?.();
  }

  respond(status: number, body: unknown) {
    this.status = status;
    this.responseText = JSON.stringify(body);
    this.onload?.();
  }
}

beforeEach(() => {
  vi.stubGlobal("XMLHttpRequest", FakeXhr);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function videoFile() {
  return new File(["contenido"], "clip de prueba.mp4", { type: "video/mp4" });
}

describe("sessions API (fetch)", () => {
  it("lista sesiones con y sin filtro de cámara", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue({ ok: true, status: 200, text: async () => "[]" });
    vi.stubGlobal("fetch", fetchMock);

    await listSessions(API);
    await listSessions(API, "cam-1");

    expect(fetchMock.mock.calls[0]?.[0]).toBe(`${API}/sessions`);
    expect(fetchMock.mock.calls[1]?.[0]).toBe(`${API}/sessions?registered_camera_id=cam-1`);
  });

  it("informa not_found al pedir una sesión inexistente", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        text: async () => JSON.stringify({ detail: { code: "not_found", message: "No existe" } }),
      }),
    );

    const error = await getSession(API, "s-1").catch((reason: unknown) => reason);
    expect((error as ApiRequestError).error).toMatchObject({ status: 404, code: "not_found" });
  });

  it("arma la URL absoluta del frame de referencia", () => {
    expect(
      referenceFrameUrl(API, {
        frame_index: 0,
        video_timestamp_seconds: 0,
        width: 1280,
        height: 720,
        url: "/sessions/s-1/reference-frame",
      }),
    ).toBe(`${API}/sessions/s-1/reference-frame`);
  });
});

describe("registerVideoSession", () => {
  it("envía el archivo crudo con los datos en la query e informa el progreso", async () => {
    const file = videoFile();
    const progress = vi.fn();
    const complete = vi.fn();

    const result = registerVideoSession(
      API,
      { name: "Sesión 1", registeredCameraId: "cam-1", file },
      { onUploadProgress: progress, onUploadComplete: complete },
    );
    const request = FakeXhr.last;
    request.upload.onprogress?.({ lengthComputable: true, loaded: 4, total: 9 });
    request.upload.onload?.();
    request.respond(201, { id: "s-1" });

    await expect(result).resolves.toEqual({ id: "s-1" });
    expect(request.method).toBe("POST");
    const url = new URL(request.url);
    expect(url.pathname).toBe("/video-sessions");
    expect(url.searchParams.get("name")).toBe("Sesión 1");
    expect(url.searchParams.get("registered_camera_id")).toBe("cam-1");
    expect(url.searchParams.get("filename")).toBe("clip de prueba.mp4");
    expect(request.headers["Content-Type"]).toBe("application/octet-stream");
    expect(request.body).toBe(file);
    expect(progress).toHaveBeenCalledWith(4, 9);
    expect(complete).toHaveBeenCalledTimes(1);
  });

  it("rechaza con el code y message de la API", async () => {
    const result = registerVideoSession(API, {
      name: "Sesión 1",
      registeredCameraId: "cam-1",
      file: videoFile(),
    });
    FakeXhr.last.respond(422, {
      detail: { code: "no_decodable_frames", message: "No se pudo decodificar ningún frame." },
    });

    const error = await result.catch((reason: unknown) => reason);
    expect(error).toBeInstanceOf(ApiRequestError);
    expect((error as ApiRequestError).error).toMatchObject({
      status: 422,
      code: "no_decodable_frames",
      message: "No se pudo decodificar ningún frame.",
    });
  });

  it("informa api_unavailable si la conexión falla", async () => {
    const result = registerVideoSession(API, {
      name: "Sesión 1",
      registeredCameraId: "cam-1",
      file: videoFile(),
    });
    FakeXhr.last.onerror?.();

    const error = await result.catch((reason: unknown) => reason);
    expect((error as ApiRequestError).error.code).toBe("api_unavailable");
  });

  it("cancela la subida con AbortSignal", async () => {
    const controller = new AbortController();
    const result = registerVideoSession(
      API,
      { name: "Sesión 1", registeredCameraId: "cam-1", file: videoFile() },
      { signal: controller.signal },
    );
    controller.abort();

    await expect(result).rejects.toMatchObject({ name: "AbortError" });
    expect(FakeXhr.last.aborted).toBe(true);
  });
});

describe("relinkVideo", () => {
  it("envía PUT a /sessions/{id}/video e informa hash_mismatch", async () => {
    const result = relinkVideo(API, "s-1", videoFile());
    const request = FakeXhr.last;
    request.respond(409, { detail: { code: "hash_mismatch", message: "Es otro archivo." } });

    const error = await result.catch((reason: unknown) => reason);
    expect(request.method).toBe("PUT");
    expect(request.url).toBe(`${API}/sessions/s-1/video`);
    expect((error as ApiRequestError).error.code).toBe("hash_mismatch");
  });
});
