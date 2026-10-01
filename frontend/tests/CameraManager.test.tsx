import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CameraManager } from "../src/components/CameraManager";
import { byButton, byLabel, changeValue, click } from "./dom";

const camera = { id: "cam-1", name: "Entrada", created_at: "2026-10-01T00:00:00Z" };
const reply = (status: number, body: unknown) => ({ ok: status < 400, status, text: async () => JSON.stringify(body) });

describe("CameraManager", () => {
  let container: HTMLDivElement;
  let root: Root;
  beforeEach(() => { container = document.createElement("div"); document.body.append(container); root = createRoot(container); });
  afterEach(async () => { await act(async () => root.unmount()); container.remove(); vi.unstubAllGlobals(); });

  async function render(status: number, body: unknown) {
    const fetchMock = vi.fn().mockResolvedValueOnce(reply(200, [camera])).mockResolvedValueOnce(reply(status, body));
    const onRenamed = vi.fn();
    const onBusyChange = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    await act(async () => root.render(<CameraManager apiBaseUrl="http://api.test" onRenamed={onRenamed} onBusyChange={onBusyChange} />));
    return { fetchMock, onRenamed, onBusyChange };
  }

  it("renombra la cámara y avisa al historial", async () => {
    const updated = { ...camera, name: "Pasillo" };
    const { onRenamed, onBusyChange } = await render(200, updated);
    await click(container.querySelector<HTMLButtonElement>('[aria-label="Editar Entrada"]')!);
    await changeValue(byLabel<HTMLInputElement>(container, "Nombre de la cámara"), "Pasillo");
    await click(byButton(container, "Guardar nombre"));
    expect(onRenamed).toHaveBeenCalledWith(updated);
    expect(container.querySelector("strong")?.textContent).toBe("Pasillo");
    expect(onBusyChange.mock.calls).toEqual([[true], [false]]);
  });

  it("elimina solo después de confirmar y retira la cámara de la lista", async () => {
    const { fetchMock } = await render(204, null);
    await click(container.querySelector<HTMLButtonElement>('[aria-label="Eliminar Entrada"]')!);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await click(byButton(container, "Eliminar cámara"));
    expect(fetchMock).toHaveBeenCalledWith("http://api.test/cameras/cam-1", { method: "DELETE" });
    expect(container.querySelector("li")).toBeNull();
  });

  it("conserva la cámara ante un análisis activo", async () => {
    await render(409, { detail: { code: "camera_has_active_jobs", message: "Hay un análisis activo." } });
    await click(container.querySelector<HTMLButtonElement>('[aria-label="Eliminar Entrada"]')!);
    await click(byButton(container, "Eliminar cámara"));
    expect(container.querySelector("li strong")?.textContent).toBe("Entrada");
    expect(container.querySelector('[role="alert"]')?.textContent).toBe("Hay un análisis activo.");
  });
});
