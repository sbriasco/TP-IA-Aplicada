import { useMemo, useSyncExternalStore } from "react";

export type Route =
  | { name: "job"; jobId: string }
  | { name: "sessions" }
  | { name: "session"; sessionId: string }
  | { name: "editor"; sessionId: string }
  | { name: "results"; sessionId: string }
  | { name: "not_found" };

const NAVIGATION_EVENT = "flowsight:navigate";
const SESSION_PATH = /^\/sessions\/([^/]+)(\/editor|\/results)?\/?$/;

export function matchRoute(pathname: string, search: string): Route {
  const jobId = (new URLSearchParams(search).get("job") ?? "").trim();
  if (jobId !== "") {
    return { name: "job", jobId };
  }
  if (pathname === "/" || pathname === "") {
    return { name: "sessions" };
  }
  const match = SESSION_PATH.exec(pathname);
  if (match === null) {
    return { name: "not_found" };
  }
  let sessionId: string;
  try {
    sessionId = decodeURIComponent(match[1]);
  } catch {
    return { name: "not_found" };
  }
  if (match[2] === "/editor") return { name: "editor", sessionId };
  if (match[2] === "/results") return { name: "results", sessionId };
  return { name: "session", sessionId };
}

/** Devuelve `false` para cancelar una navegación interna (p. ej. cambios sin guardar). */
export type NavigationGuard = () => boolean;

const guards = new Set<NavigationGuard>();

/**
 * Registra una guarda que `navigate` consulta antes de cambiar de ruta; devuelve la función que la
 * quita. Solo cubre la navegación interna: recargar o cerrar la pestaña se avisa con
 * `beforeunload`, y el botón "atrás" del navegador no pasa por acá.
 */
export function addNavigationGuard(guard: NavigationGuard): () => void {
  guards.add(guard);
  return () => {
    guards.delete(guard);
  };
}

export function navigate(path: string): void {
  const current = window.location.pathname + window.location.search;
  if (path === current) return;
  for (const guard of guards) {
    if (!guard()) return;
  }
  window.history.pushState(null, "", path);
  window.dispatchEvent(new Event(NAVIGATION_EVENT));
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener("popstate", onChange);
  window.addEventListener(NAVIGATION_EVENT, onChange);
  return () => {
    window.removeEventListener("popstate", onChange);
    window.removeEventListener(NAVIGATION_EVENT, onChange);
  };
}

function currentLocation(): string {
  return window.location.pathname + window.location.search;
}

export function useRoute(): Route {
  const location = useSyncExternalStore(subscribe, currentLocation);
  return useMemo(() => {
    const url = new URL(location, window.location.origin);
    return matchRoute(url.pathname, url.search);
  }, [location]);
}
