import { afterEach, describe, expect, it, vi } from "vitest";

import { addNavigationGuard, matchRoute, navigate } from "../src/navigation";

describe("matchRoute", () => {
  it("prioriza ?job= sobre la ruta", () => {
    expect(matchRoute("/", "?job=abc")).toEqual({ name: "job", jobId: "abc" });
    expect(matchRoute("/sessions/s1", "?job=%20abc%20")).toEqual({ name: "job", jobId: "abc" });
  });

  it("ignora ?job= vacío", () => {
    expect(matchRoute("/", "?job=")).toEqual({ name: "sessions" });
    expect(matchRoute("/", "?job=%20")).toEqual({ name: "sessions" });
  });

  it("resuelve el listado, el detalle y el editor", () => {
    expect(matchRoute("/", "")).toEqual({ name: "sessions" });
    expect(matchRoute("/sessions/s1", "")).toEqual({ name: "session", sessionId: "s1" });
    expect(matchRoute("/sessions/s1/", "")).toEqual({ name: "session", sessionId: "s1" });
    expect(matchRoute("/sessions/s1/editor", "")).toEqual({ name: "editor", sessionId: "s1" });
    expect(matchRoute("/sessions/s1/results", "")).toEqual({ name: "results", sessionId: "s1" });
    expect(matchRoute("/sessions/s1/results/", "")).toEqual({ name: "results", sessionId: "s1" });
  });

  it("decodifica el identificador de sesión", () => {
    expect(matchRoute("/sessions/a%20b", "")).toEqual({ name: "session", sessionId: "a b" });
  });

  it("marca como inexistentes las rutas desconocidas o mal codificadas", () => {
    expect(matchRoute("/sessions", "")).toEqual({ name: "not_found" });
    expect(matchRoute("/sessions/s1/otra", "")).toEqual({ name: "not_found" });
    expect(matchRoute("/sessions/s1/results/extra", "")).toEqual({ name: "not_found" });
    expect(matchRoute("/otra", "")).toEqual({ name: "not_found" });
    expect(matchRoute("/sessions/%E0%A4%A", "")).toEqual({ name: "not_found" });
  });
});

describe("navigate", () => {
  afterEach(() => {
    window.history.replaceState(null, "", "/");
  });

  it("agrega una entrada al historial y avisa a los suscriptores", () => {
    const listener = vi.fn();
    window.addEventListener("flowsight:navigate", listener);
    const length = window.history.length;

    navigate("/sessions/s1");

    expect(window.location.pathname).toBe("/sessions/s1");
    expect(window.history.length).toBe(length + 1);
    expect(listener).toHaveBeenCalledTimes(1);
    window.removeEventListener("flowsight:navigate", listener);
  });

  it("no duplica la entrada si ya está en esa ruta", () => {
    navigate("/sessions/s1");
    const listener = vi.fn();
    window.addEventListener("flowsight:navigate", listener);
    const length = window.history.length;

    navigate("/sessions/s1");

    expect(window.history.length).toBe(length);
    expect(listener).not.toHaveBeenCalled();
    window.removeEventListener("flowsight:navigate", listener);
  });

  it("no navega si una guarda lo bloquea, y vuelve a navegar al quitarla", () => {
    const guard = vi.fn(() => false);
    const remove = addNavigationGuard(guard);
    const listener = vi.fn();
    window.addEventListener("flowsight:navigate", listener);

    navigate("/sessions/s1");
    expect(guard).toHaveBeenCalledTimes(1);
    expect(window.location.pathname).toBe("/");
    expect(listener).not.toHaveBeenCalled();

    remove();
    navigate("/sessions/s1");
    expect(guard).toHaveBeenCalledTimes(1);
    expect(window.location.pathname).toBe("/sessions/s1");
    window.removeEventListener("flowsight:navigate", listener);
  });

  it("navega si todas las guardas lo permiten y no las consulta si la ruta no cambia", () => {
    const allow = vi.fn(() => true);
    const remove = addNavigationGuard(allow);

    navigate("/");
    expect(allow).not.toHaveBeenCalled();

    navigate("/sessions/s1");
    expect(allow).toHaveBeenCalledTimes(1);
    expect(window.location.pathname).toBe("/sessions/s1");
    remove();
  });
});
