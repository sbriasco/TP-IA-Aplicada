import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SessionChatPanel } from "../src/components/SessionChatPanel";

const API = "http://api.test";

const figures = [
  {
    code: "traffic_total",
    label: "visit_estimate",
    availability: "available",
    value: 17,
    unavailable_reason: null,
  },
  {
    code: "visible_occupancy",
    label: "visible",
    availability: "available",
    value: 2,
    unavailable_reason: null,
  },
  {
    code: "dwell_mean_seconds",
    label: "observable",
    availability: "unavailable",
    value: null,
    unavailable_reason: "no_closed_dwells",
  },
  {
    code: "peak",
    label: "none",
    availability: "available",
    value: null,
    unavailable_reason: null,
    start_seconds: 60,
    track_count: 5,
  },
];

function json(body: unknown) {
  return { ok: true, status: 200, text: async () => JSON.stringify(body) };
}

function reply(status: string, message: string, shownFigures = figures) {
  return {
    status,
    message,
    session_id: "s-1",
    shop_id: "shop-1",
    shop_name: "Local",
    scope: status === "answered" ? "whole_session" : null,
    figures: shownFigures,
    model_calls: status === "answered" ? 1 : 0,
  };
}

async function ask(container: HTMLDivElement, question = "¿cuál es el tráfico?") {
  const field = container.querySelector("input");
  const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
  await act(async () => {
    setValue?.call(field, question);
    field?.dispatchEvent(new Event("input", { bubbles: true }));
    field?.dispatchEvent(new Event("change", { bubbles: true }));
    container.querySelector("form")?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
  });
}

describe("SessionChatPanel", () => {
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

  it("tiene una etiqueta visible y muestra espera al enviar", async () => {
    let finish: (value: unknown) => void = () => undefined;
    const pending = new Promise((resolve) => {
      finish = resolve;
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(() => pending.then(() => json(reply("answered", "El tráfico es 17.")))),
    );

    await act(async () =>
      root.render(<SessionChatPanel apiBaseUrl={API} sessionId="s-1" shopId="shop-1" />),
    );

    const label = container.querySelector("label");
    expect(label?.textContent).toContain("Pregunta");
    expect(label?.querySelector("input")).not.toBeNull();
    expect(container.querySelector("button")?.textContent).toBe("Enviar");

    await ask(container);
    expect(container.textContent).toContain("Consultando");
    expect(container.textContent).not.toContain("El tráfico es 17.");

    await act(async () => {
      finish(undefined);
    });
  });

  it("una respuesta contestada muestra el local, toda la sesión y los rótulos", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(reply("answered", "El tráfico es 17."))));
    await act(async () =>
      root.render(<SessionChatPanel apiBaseUrl={API} sessionId="s-1" shopId="shop-1" />),
    );
    await ask(container);

    const text = container.textContent ?? "";
    expect(text).toContain("El tráfico es 17.");
    expect(text).toContain("Local");
    expect(text).toContain("toda la sesión");
    expect(text).toContain("estimación de visitas");
    expect(text).toContain("visible");
    expect(text).toContain("observable");
    expect(text).toContain("no disponible");
    expect(text).toContain("60 s");
  });

  it.each(["refused", "needs_clarification", "unavailable"])(
    "%s no muestra cifras",
    async (status) => {
      vi.stubGlobal(
        "fetch",
        vi.fn(async () => json(reply(status, "No hay cifras para mostrar."))),
      );
      await act(async () =>
        root.render(<SessionChatPanel apiBaseUrl={API} sessionId="s-1" shopId="shop-1" />),
      );
      await ask(container);

      const text = container.textContent ?? "";
      expect(text).toContain("No hay cifras para mostrar.");
      expect(text).not.toContain("estimación de visitas");
      expect(text).not.toContain("17");
    },
  );

  it("un error muestra el mensaje", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        json(reply("error", "La pregunta tardó demasiado. Podés volver a intentar.", [])),
      ),
    );
    await act(async () =>
      root.render(<SessionChatPanel apiBaseUrl={API} sessionId="s-1" shopId="shop-1" />),
    );
    await ask(container);
    expect(container.textContent).toContain("La pregunta tardó demasiado. Podés volver a intentar.");
  });
});
