import { afterEach, describe, expect, it, vi } from "vitest";

import { createCamera, listCameras } from "../src/api/cameras";
import { ApiRequestError, parseApiError } from "../src/api/http";

const API = "http://api.test";
const camera = { id: "cam-1", name: "Cam 01", created_at: "2026-09-28T00:00:00Z" };

function jsonResponse(status: number, body: unknown) {
  return { ok: status >= 200 && status < 300, status, text: async () => JSON.stringify(body) };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("parseApiError", () => {
  it("lee errores HTTP con detail y conserva los campos extra", () => {
    expect(
      parseApiError(409, { detail: { code: "camera_exists", message: "Ya existe", existing_camera: camera } }),
    ).toEqual({
      status: 409,
      code: "camera_exists",
      message: "Ya existe",
      extra: { existing_camera: camera },
    });
  });

  it("lee el 422 de validación plano", () => {
    expect(parseApiError(422, { code: "validation_error", message: "Dato inválido" })).toEqual({
      status: 422,
      code: "validation_error",
      message: "Dato inválido",
      extra: {},
    });
  });

  it("usa un código genérico si el cuerpo no tiene el formato esperado", () => {
    expect(parseApiError(405, { detail: "Method Not Allowed" }).code).toBe("unexpected_response");
    expect(parseApiError(500, undefined).code).toBe("unexpected_response");
  });
});

describe("cameras API", () => {
  it("lista las cámaras", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, [camera]));
    vi.stubGlobal("fetch", fetchMock);

    await expect(listCameras(API)).resolves.toEqual([camera]);
    expect(fetchMock).toHaveBeenCalledWith(`${API}/cameras`, undefined);
  });

  it("crea una cámara", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(201, camera));
    vi.stubGlobal("fetch", fetchMock);

    await expect(createCamera(API, "Cam 01")).resolves.toEqual({ camera, existed: false });
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ name: "Cam 01" }));
  });

  it("devuelve la cámara existente ante camera_exists", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(409, {
          detail: { code: "camera_exists", message: "Ya existe", existing_camera: camera },
        }),
      ),
    );

    await expect(createCamera(API, " cam 01 ")).resolves.toEqual({ camera, existed: true });
  });

  it("propaga otros errores con code y message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(422, { code: "validation_error", message: "Nombre vacío" })),
    );

    const error = await createCamera(API, "").catch((reason: unknown) => reason);
    expect(error).toBeInstanceOf(ApiRequestError);
    expect((error as ApiRequestError).error).toMatchObject({ status: 422, code: "validation_error" });
  });

  it("informa api_unavailable si no hay conexión", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));

    const error = await listCameras(API).catch((reason: unknown) => reason);
    expect((error as ApiRequestError).error).toMatchObject({ status: 0, code: "api_unavailable" });
  });
});
