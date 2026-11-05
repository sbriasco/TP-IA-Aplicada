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

  it("conserva la respuesta y permite reintentar un refresco de historial rechazado", async () => {
    let historyRequests = 0;
    let chatRequests = 0;
    vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL) => {
      if (String(url).endsWith("/chat-threads")) {
        historyRequests += 1;
        if (historyRequests === 2) throw new TypeError("Failed to fetch");
        return json([{
          id: "thread-1", session_id: "s-1", shop_id: "shop-1", title: "Tráfico guardado",
          created_at: "2026-10-30T00:00:00Z", updated_at: "2026-10-30T00:00:00Z",
        }]);
      }
      chatRequests += 1;
      return json(reply("answered", "El tráfico es 17."));
    }));
    await act(async () => root.render(<SessionChatPanel apiBaseUrl={API} sessionId="s-1" shopId="shop-1" />));

    await ask(container);
    expect(container.querySelector('[role="log"]')?.textContent).toContain("El tráfico es 17.");
    const status = container.querySelector('[role="status"]');
    expect(status?.textContent).toContain("No se pudo actualizar el historial");
    const retry = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent === "Reintentar historial",
    );
    expect(retry).toBeDefined();
    const openHistory = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent?.includes("Historial"),
    );
    await act(async () => openHistory?.click());
    expect(container.querySelector('[aria-label="Conversaciones de esta sesión"]')?.textContent).toContain("Tráfico guardado");

    await act(async () => retry?.click());
    expect(historyRequests).toBe(3);
    expect(chatRequests).toBe(1);
    expect(container.querySelector('[role="status"]')).toBeNull();
    expect(container.querySelector('[role="log"]')?.textContent).toContain("El tráfico es 17.");
  });

  it.each(["hola", "¿cómo uso FlowSight?"])("permite conversar sin zona: %s", async (question) => {
    const fetch = mockFetch(async () => json({
      ...reply("answered", "Puedo ayudarte con FlowSight.", []),
      shop_id: null, shop_name: null, scope: null,
    }));
    vi.stubGlobal("fetch", fetch);
    await act(async () => root.render(<SessionChatPanel apiBaseUrl={API} sessionId="s-1" shopId={null} />));

    expect(container.querySelector("input")?.disabled).toBe(false);
    expect(container.textContent).toContain("Sin zona seleccionada");
    await ask(container, question);

    const chatCall = fetch.mock.calls.find(([url]) => String(url) === `${API}/chat`);
    expect(chatCall).toBeDefined();
    expect(container.querySelector('[role="log"]')?.textContent).toContain("Puedo ayudarte con FlowSight.");
  });

  it("conserva el hilo al repreguntar sin zona y lo limpia al cambiar de sesión", async () => {
    const requests: unknown[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      if (String(url).endsWith("/chat-threads")) return json([]);
      requests.push(JSON.parse(String(init?.body)));
      return json({ ...reply("answered", "Te ayudo con FlowSight.", []), shop_id: null, shop_name: null, scope: null });
    }));
    await act(async () => root.render(<SessionChatPanel apiBaseUrl={API} sessionId="s-1" shopId={null} />));
    await ask(container, "hola");
    await ask(container, "¿cómo configuro zonas?");
    expect(requests).toEqual([
      { question: "hola", session_id: "s-1", shop_id: null },
      { question: "¿cómo configuro zonas?", session_id: "s-1", shop_id: null, thread_id: "thread-1" },
    ]);

    await act(async () => root.render(<SessionChatPanel apiBaseUrl={API} sessionId="s-2" shopId={null} />));
    expect(container.querySelector('[role="log"]')?.textContent).not.toContain("Te ayudo con FlowSight.");
    await ask(container, "hola otra vez");
    expect(requests.at(-1)).toEqual({ question: "hola otra vez", session_id: "s-2", shop_id: null });
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

  it("oculta el historial por defecto y lo muestra al abrirlo", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/sessions/") && url.includes("/chat-threads")) {
          return json([
            {
              id: "thread-1",
              session_id: "s-1",
              shop_id: "shop-1",
              title: "Tráfico de la mañana",
              created_at: "2026-10-30T00:00:00Z",
              updated_at: "2026-10-30T00:00:00Z",
            },
          ]);
        }
        return json({
          thread: {
            id: "thread-1",
            session_id: "s-1",
            shop_id: "shop-1",
            title: "Tráfico de la mañana",
            created_at: "2026-10-30T00:00:00Z",
            updated_at: "2026-10-30T00:00:00Z",
          },
          messages: [],
        });
      }),
    );

    await act(async () =>
      root.render(<SessionChatPanel apiBaseUrl={API} sessionId="s-1" shopId="shop-1" />),
    );
    await act(async () => undefined);

    expect(container.querySelector('[aria-label="Conversaciones de esta sesión"]')).toBeNull();
    expect(container.textContent).not.toContain("Todavía no hay conversaciones.");
    expect(container.textContent).not.toContain("Tráfico de la mañana");

    const openHistory = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent?.includes("Historial"),
    );
    expect(openHistory?.getAttribute("aria-expanded")).toBe("false");

    await act(async () => {
      openHistory?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    const history = container.querySelector('[aria-label="Conversaciones de esta sesión"]');
    expect(history).not.toBeNull();
    expect(history?.textContent).toContain("Tráfico de la mañana");
    expect(
      Array.from(container.querySelectorAll("button")).some(
        (button) => button.getAttribute("aria-label") === "Ocultar historial",
      ),
    ).toBe(true);
  });

  it("muestra el vacío del historial al abrirlo sin hilos", async () => {
    vi.stubGlobal("fetch", mockFetch(async () => json(reply("answered", "ok"))));
    await act(async () =>
      root.render(<SessionChatPanel apiBaseUrl={API} sessionId="s-1" shopId="shop-1" />),
    );
    await act(async () => undefined);

    expect(container.querySelector('[aria-label="Conversaciones de esta sesión"]')).toBeNull();

    const openHistory = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent?.includes("Historial"),
    );
    await act(async () => {
      openHistory?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(container.textContent).toContain("Todavía no hay conversaciones.");
  });

  it("permite nueva conversación con el historial cerrado", async () => {
    vi.stubGlobal("fetch", mockFetch(async () => json(reply("answered", "El tráfico es 17."))));
    await act(async () =>
      root.render(<SessionChatPanel apiBaseUrl={API} sessionId="s-1" shopId="shop-1" />),
    );
    await ask(container);
    expect(container.querySelector('[role="log"]')?.textContent).toContain("¿cuál es el tráfico?");

    const newConversation = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent?.includes("Nueva conversación"),
    );
    expect(newConversation).toBeDefined();
    expect(container.querySelector('[aria-label="Conversaciones de esta sesión"]')).toBeNull();

    await act(async () => {
      newConversation?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(container.querySelector('[role="log"]')?.textContent).not.toContain("¿cuál es el tráfico?");
    expect(container.textContent).toContain("Hola, puedo citar métricas");
  });

  it("separa la nueva conversación de un envío pendiente y recupera el hilo guardado en el historial", async () => {
    let finishOld: () => void = () => undefined;
    let finishEarlierRefresh: () => void = () => undefined;
    const pendingOld = new Promise<void>((resolve) => { finishOld = resolve; });
    const earlierRefresh = new Promise<void>((resolve) => { finishEarlierRefresh = resolve; });
    let savedOld = false;
    let historyRequests = 0;
    const requests: unknown[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      if (String(url).endsWith("/chat-threads")) {
        historyRequests++;
        if (historyRequests === 2) {
          await earlierRefresh;
          return json([]);
        }
        return json(savedOld ? [{
          id: "thread-1", session_id: "s-1", shop_id: "shop-1", title: "Conversación anterior",
          created_at: "2026-10-30T00:00:00Z", updated_at: "2026-10-30T00:00:00Z",
        }] : []);
      }
      const body = JSON.parse(String(init?.body)) as { question: string };
      requests.push(body);
      if (body.question === "Consulta anterior") {
        await pendingOld;
        savedOld = true;
        return json(reply("answered", "Respuesta anterior"));
      }
      return json({ ...reply("answered", "Respuesta nueva"), thread_id: "thread-new" });
    }));
    await act(async () => root.render(<SessionChatPanel apiBaseUrl={API} sessionId="s-1" shopId="shop-1" />));
    await ask(container, "Consulta anterior");

    const log = container.querySelector('[role="log"]');
    expect(log?.getAttribute("aria-busy")).toBe("true");
    const newConversation = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent === "Nueva conversación",
    );
    await act(async () => newConversation?.click());
    expect(log?.getAttribute("aria-busy")).toBe("false");
    await ask(container, "Consulta nueva");
    expect(log?.textContent).toContain("Respuesta nueva");

    await act(async () => finishOld());
    await act(async () => finishEarlierRefresh());
    expect(log?.textContent).not.toContain("Respuesta anterior");
    const openHistory = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent === "Historial",
    );
    await act(async () => openHistory?.click());
    expect(container.querySelector('nav[aria-label="Conversaciones de esta sesión"]')?.textContent).toContain("Conversación anterior");

    await ask(container, "Repregunta nueva");
    expect(requests).toEqual([
      { question: "Consulta anterior", session_id: "s-1", shop_id: "shop-1" },
      { question: "Consulta nueva", session_id: "s-1", shop_id: "shop-1" },
      { question: "Repregunta nueva", session_id: "s-1", shop_id: "shop-1", thread_id: "thread-new" },
    ]);
  });

  it("ignora una reapertura pendiente sin interrumpir la espera de un envío nuevo", async () => {
    let finishOpen: () => void = () => undefined;
    let finishPost: () => void = () => undefined;
    const pendingOpen = new Promise<void>((resolve) => { finishOpen = resolve; });
    const pendingPost = new Promise<void>((resolve) => { finishPost = resolve; });
    const thread = {
      id: "thread-1", session_id: "s-1", shop_id: "shop-1", title: "Conversación guardada",
      created_at: "2026-10-30T00:00:00Z", updated_at: "2026-10-30T00:00:00Z",
    };
    vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL) => {
      if (String(url).endsWith("/chat-threads")) return json([thread]);
      if (String(url).endsWith("/chat-threads/thread-1")) {
        await pendingOpen;
        return json({ thread, messages: [{ role: "user", content: "Pregunta guardada" }] });
      }
      await pendingPost;
      return json({ ...reply("answered", "Respuesta nueva"), thread_id: "thread-new" });
    }));
    await act(async () => root.render(<SessionChatPanel apiBaseUrl={API} sessionId="s-1" shopId="shop-1" />));
    const click = async (name: string) => {
      const button = Array.from(container.querySelectorAll("button")).find((item) => item.textContent === name);
      expect(button).toBeDefined();
      await act(async () => button?.click());
    };
    await click("Historial");
    await click("Conversación guardada");
    await click("Nueva conversación");
    await ask(container, "Consulta nueva");
    await act(async () => finishOpen());

    const log = container.querySelector('[role="log"]');
    expect(log?.getAttribute("aria-busy")).toBe("true");
    expect(log?.textContent).toContain("Consulta nueva");
    expect(log?.textContent).not.toContain("Pregunta guardada");
    await act(async () => finishPost());
    expect(log?.getAttribute("aria-busy")).toBe("false");
    expect(log?.textContent).toContain("Respuesta nueva");
  });
});
