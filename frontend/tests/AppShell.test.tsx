import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { AppShell } from "../src/components/AppShell";

describe("AppShell", () => {
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

    expect(container.querySelector("header")?.textContent).toBe("Resultados");
  });
});
