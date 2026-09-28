import { useMemo, useSyncExternalStore } from "react";

export type Route =
  | { name: "job"; jobId: string }
  | { name: "sessions" }
  | { name: "session"; sessionId: string }
  | { name: "editor"; sessionId: string }
  | { name: "not_found" };

const NAVIGATION_EVENT = "flowsight:navigate";
const SESSION_PATH = /^\/sessions\/([^/]+)(\/editor)?\/?$/;

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
  return match[2] === undefined ? { name: "session", sessionId } : { name: "editor", sessionId };
}

export function navigate(path: string): void {
  const current = window.location.pathname + window.location.search;
  if (path === current) return;
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
