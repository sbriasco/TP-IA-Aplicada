import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CameraPicker } from "../src/components/CameraPicker";
import { byButton, byLabel, changeValue, click } from "./dom";

const API = "http://api.test";
const cam01 = { id: "cam-1", name: "Cam 01", created_at: "2026-09-28T00:00:00Z" };
const pasillo = { id: "cam-2", name: "Pasillo", created_at: "2026-09-28T00:00:00Z" };

function response(status: number, body: unknown) {
  return { ok: status >= 200 && status < 300, status, text: async () => JSON.stringify(body) };
}

describe("CameraPicker", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
    vi.unstubAllGlobals();
  });

  it("lista las cámaras y avisa el cambio de selección", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(200, [cam01, pasillo])));
    const onChange = vi.fn();

    await act(async () => root.render(<CameraPicker apiBaseUrl={API} value="" onChange={onChange} />));
    const select = byLabel<HTMLSelectElement>(container, "Cámara");
    expect(Array.from(select.options).map((option) => option.text)).toEqual([
      "Elegí una cámara",
      "Cam 01",
      "Pasillo",
    ]);

    await changeValue(select, "cam-2");
    expect(onChange).toHaveBeenCalledWith("cam-2");
  });

  it("crea una cámara nueva y la selecciona", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(200, [pasillo]))
      .mockResolvedValueOnce(response(201, cam01));
    vi.stubGlobal("fetch", fetchMock);
    const onChange = vi.fn();

    await act(async () => root.render(<CameraPicker apiBaseUrl={API} value="" onChange={onChange} />));
    await changeValue(byLabel<HTMLInputElement>(container, "Nombre de la cámara"), "Cam 01");
    await click(byButton(container, "Crear cámara"));

    expect(onChange).toHaveBeenCalledWith("cam-1");
    expect(container.querySelector('[role="status"]')?.textContent).toBe(
      "Cámara «Cam 01» creada y seleccionada.",
    );
    const options = Array.from(byLabel<HTMLSelectElement>(container, "Cámara").options);
    expect(options.map((option) => option.text)).toEqual(["Elegí una cámara", "Cam 01", "Pasillo"]);
  });

  it("ante camera_exists selecciona la existente y lo informa", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(response(200, [cam01]))
        .mockResolvedValueOnce(
          response(409, {
            detail: { code: "camera_exists", message: "Ya existe", existing_camera: cam01 },
          }),
        ),
    );
    const onChange = vi.fn();

    await act(async () => root.render(<CameraPicker apiBaseUrl={API} value="" onChange={onChange} />));
    await changeValue(byLabel<HTMLInputElement>(container, "Nombre de la cámara"), " cam 01 ");
    await click(byButton(container, "Crear cámara"));

    expect(onChange).toHaveBeenCalledWith("cam-1");
    expect(container.querySelector('[role="status"]')?.textContent).toBe(
      "Ya existía la cámara «Cam 01»; quedó seleccionada.",
    );
    expect(byLabel<HTMLSelectElement>(container, "Cámara").options).toHaveLength(2);
  });

  it("muestra el mensaje de la API si no puede crear la cámara", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(response(200, []))
        .mockResolvedValueOnce(response(422, { code: "validation_error", message: "Nombre inválido" })),
    );

    await act(async () => root.render(<CameraPicker apiBaseUrl={API} value="" onChange={vi.fn()} />));
    await changeValue(byLabel<HTMLInputElement>(container, "Nombre de la cámara"), "x");
    await click(byButton(container, "Crear cámara"));

    expect(container.querySelector('[role="alert"]')?.textContent).toBe("Nombre inválido");
  });
});
