import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { click } from "./dom";

import { AppShell } from "../src/components/AppShell";

describe("AppShell", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    localStorage.removeItem("flowsight-theme");
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
    localStorage.removeItem("flowsight-theme");
    document.documentElement.removeAttribute("data-theme");
    document.documentElement.classList.remove("dark");
  });

  it("alterna el tema y conserva la preferencia al volver a montar", async () => {
    await act(async () => root.render(<AppShell title="Análisis">Contenido</AppShell>));
    await click(container.querySelector('button[aria-label="Activar modo oscuro"]')!);
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem("flowsight-theme")).toBe("dark");
    await act(async () => root.unmount());
    root = createRoot(container);
    await act(async () => root.render(<AppShell title="Otra vista">Contenido</AppShell>));
    expect(container.querySelector('button[aria-label="Activar modo claro"]')).not.toBeNull();
    await click(container.querySelector('button[aria-label="Activar modo claro"]')!);
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("pone el título en el único h1 y el contexto al lado", async () => {
    await act(async () => {
      root.render(
        <AppShell title="Sesiones" context="2 registradas">
          <p>Cuerpo</p>
        </AppShell>,
      );
    });

    expect(container.querySelectorAll("h1")).toHaveLength(1);
    expect(container.querySelector("h1")?.textContent).toBe("Sesiones");
    expect(container.querySelector("header")?.textContent).toContain("2 registradas");
    expect(container.querySelector("main")?.textContent).toContain("Cuerpo");
  });

  it("omite el contexto vacío", async () => {
    await act(async () => {
      root.render(<AppShell title="Resultados">{null}</AppShell>);
    });

    expect(container.querySelector("[data-context]")).toBeNull();
  });

  it("ofrece un acceso al contenido y navegación entre las etapas de la sesión", async () => {
    await act(async () => {
      root.render(<AppShell title="Mañana" context="Editor" sessionId="s 1">Contenido</AppShell>);
    });
    const skip = container.querySelector<HTMLAnchorElement>('a[href="#main-content"]');
    expect(skip).not.toBeNull();
    expect(container.querySelector("main")?.id).toBe("main-content");
    const nav = container.querySelector('nav[aria-label="Sesión"]');
    expect(nav?.querySelector('a[aria-current="page"]')?.getAttribute("href")).toBe("/sessions/s%201/editor");
    expect(nav?.querySelector('a[href="/sessions/s%201/results"]')).not.toBeNull();
  });
});
