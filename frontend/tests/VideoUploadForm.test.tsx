import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { VideoUploadForm } from "../src/components/VideoUploadForm";
import { byButton, byLabel, changeValue, chooseFile, click, submit } from "./dom";

const API = "http://api.test";
const camera = { id: "cam-1", name: "Cam 01", created_at: "2026-09-28T00:00:00Z" };

class FakeXhr {
  static instances: FakeXhr[] = [];
  url = "";
  status = 0;
  responseText = "";
  upload: {
    onprogress?: (event: { lengthComputable: boolean; loaded: number; total: number }) => void;
    onload?: () => void;
  } = {};
  onload?: () => void;
  onerror?: () => void;
  onabort?: () => void;

  constructor() {
    FakeXhr.instances.push(this);
  }

  open(_method: string, url: string) {
    this.url = url;
  }

  setRequestHeader() {}

  send() {}

  abort() {
    this.onabort?.();
  }
}

describe("VideoUploadForm", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    FakeXhr.instances = [];
    vi.stubGlobal("XMLHttpRequest", FakeXhr);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, status: 200, text: async () => JSON.stringify([camera]) }),
    );
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
    vi.unstubAllGlobals();
  });

  async function fillForm(file: File) {
    await chooseFile(byLabel<HTMLInputElement>(container, "Archivo de video"), file);
    await changeValue(byLabel<HTMLInputElement>(container, "Nombre de la sesión"), "Sesión 1");
    await changeValue(byLabel<HTMLSelectElement>(container, "Cámara asignada"), "cam-1");
  }

  async function sentRequest(): Promise<FakeXhr> {
    await act(async () => {
      await vi.waitFor(() => expect(FakeXhr.instances).toHaveLength(1));
    });
    return FakeXhr.instances[0]!;
  }

  function form() {
    return container.querySelector("form") as HTMLFormElement;
  }

  it("limita los formatos aceptados por el selector", async () => {
    await act(async () => root.render(<VideoUploadForm apiBaseUrl={API} onRegistered={vi.fn()} />));

    expect(byLabel<HTMLInputElement>(container, "Archivo de video").accept).toBe(
      ".mp4,.mpg,.mpeg,.avi,.mov,.mkv",
    );
  });

  it("muestra el archivo elegido, permite quitarlo y cancela sin iniciar la subida", async () => {
    const cancel = vi.fn();
    await act(async () => root.render(<VideoUploadForm apiBaseUrl={API} onRegistered={vi.fn()} onCancel={cancel} />));
    await chooseFile(byLabel<HTMLInputElement>(container, "Archivo de video"), new File(["video"], "entrada.mp4"));
    expect(container.textContent).toContain("entrada.mp4");
    await click(byButton(container, "Quitar archivo"));
    expect(container.textContent).not.toContain("entrada.mp4");
    await click(byButton(container, "Cancelar"));
    expect(cancel).toHaveBeenCalledOnce();
    expect(FakeXhr.instances).toHaveLength(0);
  });

  it("acepta un archivo arrastrado y conserva la petición de registro existente", async () => {
    await act(async () => root.render(<VideoUploadForm apiBaseUrl={API} onRegistered={vi.fn()} />));
    const file = new File(["video"], "arrastrado.mp4");
    const drop = new Event("drop", { bubbles: true, cancelable: true });
    Object.defineProperty(drop, "dataTransfer", { value: { files: [file], types: ["Files"] } });
    await act(async () => { container.querySelector('[aria-label="Soltar archivo de video"]')!.dispatchEvent(drop); });
    expect(container.textContent).toContain("arrastrado.mp4");
    await changeValue(byLabel<HTMLInputElement>(container, "Nombre de la sesión"), "Entrada");
    await changeValue(byLabel<HTMLSelectElement>(container, "Cámara asignada"), "cam-1");
    await submit(form());
    const request = await sentRequest();
    expect(new URL(request.url).searchParams.get("name")).toBe("Entrada");
    expect(new URL(request.url).searchParams.get("filename")).toBe("arrastrado.mp4");
  });

  it("muestra el progreso de subida, luego el análisis, y entrega la sesión", async () => {
    const onRegistered = vi.fn();
    await act(async () =>
      root.render(<VideoUploadForm apiBaseUrl={API} onRegistered={onRegistered} />),
    );
    await fillForm(new File(["0123456789"], "clip.mp4"));
    await submit(form());

    const request = await sentRequest();
    expect(new URL(request.url).searchParams.get("name")).toBe("Sesión 1");

    await act(async () =>
      request.upload.onprogress?.({ lengthComputable: true, loaded: 5, total: 10 }),
    );
    const progress = container.querySelector("progress") as HTMLProgressElement;
    expect(progress.value).toBe(5);
    expect(progress.max).toBe(10);
    expect(container.querySelector('[role="status"]')?.textContent).toContain("50 %");

    await act(async () => request.upload.onload?.());
    expect(container.querySelector('[role="status"]')?.textContent).toContain("Analizando video…");
    expect(container.querySelector("progress")?.hasAttribute("value")).toBe(false);

    await act(async () => {
      request.status = 201;
      request.responseText = JSON.stringify({ id: "s-1" });
      request.onload?.();
    });
    expect(onRegistered).toHaveBeenCalledWith({ id: "s-1" });
  });

  it("muestra el mensaje de la API y permite reintentar", async () => {
    await act(async () => root.render(<VideoUploadForm apiBaseUrl={API} onRegistered={vi.fn()} />));
    await fillForm(new File(["x"], "clip.mp4"));
    await submit(form());

    const request = await sentRequest();
    await act(async () => {
      request.status = 422;
      request.responseText = JSON.stringify({
        detail: { code: "unsupported_format", message: "Formato no admitido. Convertí el video a MP4." },
      });
      request.onload?.();
    });

    expect(container.querySelector('[role="alert"]')?.textContent).toBe(
      "Formato no admitido. Convertí el video a MP4.",
    );
    expect(container.querySelector("fieldset")?.disabled).toBe(false);
    expect(container.querySelector("progress")).toBeNull();
  });

  it("no llama a la API si no puede leer el archivo elegido", async () => {
    await act(async () => root.render(<VideoUploadForm apiBaseUrl={API} onRegistered={vi.fn()} />));
    vi.stubGlobal(
      "FileReader",
      class {
        onload?: () => void;
        onerror?: () => void;
        readAsArrayBuffer() {
          queueMicrotask(() => this.onerror?.());
        }
      },
    );
    await fillForm(new File(["x"], "clip.mp4"));
    await submit(form());
    await act(async () => {
      await vi.waitFor(() => expect(container.querySelector('[role="alert"]')).not.toBeNull());
    });

    expect(container.querySelector('[role="alert"]')?.textContent).toBe(
      "No se pudo leer el archivo elegido.",
    );
    expect(FakeXhr.instances).toHaveLength(0);
  });
});
