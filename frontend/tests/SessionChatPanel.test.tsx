import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ChatFigure } from "../src/api/chat";
import { SessionChatPanel } from "../src/components/SessionChatPanel";

const API = "http://api.test";

const figures: ChatFigure[] = [
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

function reply(status: string, message: string, shownFigures: ChatFigure[] = figures) {
  return {
    status,
    message,
    session_id: "s-1",
    shop_id: "shop-1",
    shop_name: "Local",
    scope: status === "answered" ? "whole_session" : null,
    figures: shownFigures,
    model_calls: status === "answered" ? 1 : 0,
    thread_id: "thread-1",
  };
}

function mockFetch(postImpl: () => Promise<unknown>) {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/sessions/") && url.includes("/chat-threads")) {
      return json([]);
    }
    if (url.includes("/chat-threads/")) {
      return json({
        thread: {
          id: "thread-1",
          session_id: "s-1",
          shop_id: "shop-1",
          title: "Hilo",
          created_at: "2026-10-30T00:00:00Z",
          updated_at: "2026-10-30T00:00:00Z",
        },
        messages: [],
      });
    }
    return postImpl();
  });
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
      mockFetch(() => pending.then(() => json(reply("answered", "El tráfico es 17.")))),
    );

    await act(async () =>
      root.render(<SessionChatPanel apiBaseUrl={API} sessionId="s-1" shopId="shop-1" />),
    );

    const label = container.querySelector("label");
    expect(label?.textContent).toContain("Pregunta");
    expect(label?.getAttribute("for")).toBe(container.querySelector("input")?.id);
    expect(container.querySelector('button[type="submit"]')?.textContent).toBe("Enviar");

    await ask(container);
    expect(container.textContent).toContain("Consultando");
    expect(container.textContent).not.toContain("El tráfico es 17.");

    await act(async () => {
      finish(undefined);
    });
  });

  it("una respuesta contestada muestra el local, toda la sesión y los rótulos", async () => {
    vi.stubGlobal("fetch", mockFetch(async () => json(reply("answered", "El tráfico es 17."))));
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
        mockFetch(async () => json(reply(status, "No hay cifras para mostrar."))),
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
      mockFetch(async () =>
        json(reply("error", "La pregunta tardó demasiado. Podés volver a intentar.", [])),
      ),
    );
    await act(async () =>
      root.render(<SessionChatPanel apiBaseUrl={API} sessionId="s-1" shopId="shop-1" />),
    );
    await ask(container);
    expect(container.textContent).toContain("La pregunta tardó demasiado. Podés volver a intentar.");
  });

  it("se identifica como agente de IA y conserva los turnos de la conversación", async () => {
    vi.stubGlobal("fetch", mockFetch(async () => json(reply("answered", "El tráfico es 17."))));
    await act(async () => root.render(<SessionChatPanel apiBaseUrl={API} sessionId="s-1" shopId="shop-1" />));
    expect(container.textContent).toContain("Agente FlowSight");
    expect(container.textContent).toContain("Consultas sobre este análisis");
    await ask(container, "¿cuál es el tráfico?");
    await ask(container, "¿cuál fue el horario pico?");
    const log = container.querySelector('[role="log"]');
    expect(log?.textContent).toContain("¿cuál es el tráfico?");
    expect(log?.textContent).toContain("¿cuál fue el horario pico?");
    expect(log?.querySelectorAll('[aria-label="Respuesta"]')).toHaveLength(2);
  });

  it("muestra contraste y eje cuando el alcance es comparison", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch(async () =>
        json({
          ...reply("answered", "Primera tuvo más tráfico (17 vs 5).", [
            {
              code: "traffic_total",
              label: "visit_estimate",
              availability: "available",
              value: 17,
              unavailable_reason: null,
              estimation: true,
            },
          ]),
          scope: "comparison",
          comparison: {
            axis: "session",
            column_labels: ["Primera", "Segunda"],
            insight_codes: ["higher_traffic_total"],
          },
        }),
      ),
    );
    await act(async () =>
      root.render(<SessionChatPanel apiBaseUrl={API} sessionId="s-1" shopId="shop-1" />),
    );
    await ask(container, "compará el tráfico con la última");
    const text = container.textContent ?? "";
    expect(text).toContain("contraste");
    expect(text).toContain("session");
    expect(text).toContain("Primera vs Segunda");
    expect(text).toContain("estimación");
  });

  it("descarta una respuesta pendiente al cambiar el local", async () => {
    let finish: (value: unknown) => void = () => undefined;
    const pending = new Promise((resolve) => { finish = resolve; });
    vi.stubGlobal("fetch", mockFetch(() => pending.then(() => json(reply("answered", "Respuesta del local anterior")))));
    await act(async () => root.render(<SessionChatPanel apiBaseUrl={API} sessionId="s-1" shopId="shop-1" />));
    await ask(container);
    await act(async () => root.render(<SessionChatPanel apiBaseUrl={API} sessionId="s-1" shopId="shop-2" />));
    await act(async () => finish(undefined));
    expect(container.textContent).not.toContain("Respuesta del local anterior");
    expect(container.textContent).not.toContain("¿cuál es el tráfico?");
    expect(container.querySelector('button[type="submit"]')?.hasAttribute("disabled")).toBe(true);
  });
});
