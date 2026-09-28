import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiRequestError } from "../src/api/http";
import {
  aspectRatioMismatch,
  createSceneVersion,
  createVideoAnalysisJob,
  getSceneVersion,
  listSceneVersions,
} from "../src/api/scenes";
import type { SceneIssue, SceneVersion, SceneVersionCreate, SceneVersionSummary } from "../src/types/scene";

const API = "http://api.test";

function jsonResponse(status: number, body: unknown) {
  return { ok: status >= 200 && status < 300, status, text: async () => JSON.stringify(body) };
}

const summary: SceneVersionSummary = {
  id: "v-2",
  camera_id: "cam-1",
  version_number: 2,
  reference_session_id: "s-1",
  frame_width: 1280,
  frame_height: 720,
  created_by_machine_id: "pc-lab-01",
  created_at: "2026-09-28T10:00:00Z",
  shop_count: 1,
};

const version: SceneVersion = {
  ...summary,
  shops: [
    {
      shop_id: "shop-1",
      name: "Local A",
      zones: {
        front: [
          [0.1, 0.1],
          [0.3, 0.1],
          [0.3, 0.3],
        ],
      },
      entry_line: { start: [0.1, 0.4], end: [0.3, 0.4], entry_direction: "a_to_b" },
    },
  ],
};

const warning: SceneIssue = {
  rule: "zones_overlap",
  element: "zone:front",
  shop_index: 0,
  shop_name: "Local A",
  message: "Las zonas se superponen.",
};

const payload: SceneVersionCreate = {
  reference_session_id: "s-1",
  base_version_id: "v-1",
  shops: [
    {
      shop_id: null,
      name: "Local A",
      zones: version.shops[0]!.zones,
      entry_line: version.shops[0]!.entry_line,
    },
  ],
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("scenes API", () => {
  it("lista las versiones de una cámara", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, [summary]));
    vi.stubGlobal("fetch", fetchMock);

    await expect(listSceneVersions(API, "cam 1")).resolves.toEqual([summary]);
    expect(fetchMock).toHaveBeenCalledWith(`${API}/cameras/cam%201/scene-versions`, undefined);
  });

  it("obtiene una versión", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, version));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getSceneVersion(API, "v-2")).resolves.toEqual(version);
    expect(fetchMock).toHaveBeenCalledWith(`${API}/scene-versions/v-2`, undefined);
  });

  it("crea una versión y separa las advertencias", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse(201, { ...version, warnings: [warning] }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(createSceneVersion(API, "cam-1", payload)).resolves.toEqual({
      ok: true,
      version,
      warnings: [warning],
    });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${API}/cameras/cam-1/scene-versions`);
    expect(init.method).toBe("POST");
    expect(init.headers).toEqual({ "Content-Type": "application/json" });
    expect(JSON.parse(init.body as string)).toEqual(payload);
  });

  it("devuelve todos los errores ante invalid_scene_configuration", async () => {
    const errors: SceneIssue[] = [
      { rule: "no_shops", element: "version", shop_index: null, shop_name: null, message: "Sin locales." },
      { ...warning, rule: "too_few_vertices", message: "Pocos vértices." },
    ];
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(422, {
          detail: { code: "invalid_scene_configuration", message: "Tiene errores", errors },
        }),
      ),
    );

    await expect(createSceneVersion(API, "cam-1", payload)).resolves.toEqual({ ok: false, errors });
  });

  it("propaga los demás errores al crear una versión", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(422, { code: "validation_error", message: "Demasiados locales" }),
      ),
    );

    const error = await createSceneVersion(API, "cam-1", payload).catch((reason: unknown) => reason);
    expect(error).toBeInstanceOf(ApiRequestError);
    expect((error as ApiRequestError).error).toMatchObject({ status: 422, code: "validation_error" });
  });

  it("crea un trabajo video_analysis con la versión elegida", async () => {
    const job = {
      id: "job-1",
      session_id: "s-1",
      kind: "video_analysis",
      scene_version_id: "v-1",
      status: "pending",
      created_at: "2026-09-28T11:00:00Z",
    };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(201, job));
    vi.stubGlobal("fetch", fetchMock);

    await expect(createVideoAnalysisJob(API, "s-1", "v-1")).resolves.toMatchObject(job);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${API}/sessions/s-1/jobs`);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ kind: "video_analysis", scene_version_id: "v-1" });
  });

  it("propaga aspect_ratio_mismatch con los dos ratios", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(409, {
          detail: {
            code: "aspect_ratio_mismatch",
            message: "Creá una versión nueva",
            video_aspect_ratio: 1.333333,
            version_aspect_ratio: 1.777778,
          },
        }),
      ),
    );

    const error = await createVideoAnalysisJob(API, "s-1", "v-1").catch((reason: unknown) => reason);
    expect(error).toBeInstanceOf(ApiRequestError);
    const apiError = (error as ApiRequestError).error;
    expect(apiError).toMatchObject({ status: 409, code: "aspect_ratio_mismatch" });
    expect(aspectRatioMismatch(apiError)).toEqual({ video: 1.333333, version: 1.777778 });
  });

  it("no inventa ratios si faltan o el código es otro", () => {
    expect(
      aspectRatioMismatch({ status: 409, code: "scene_not_configured", message: "x", extra: {} }),
    ).toBeNull();
    expect(
      aspectRatioMismatch({
        status: 409,
        code: "aspect_ratio_mismatch",
        message: "x",
        extra: { video_aspect_ratio: "1.3" },
      }),
    ).toBeNull();
  });
});
