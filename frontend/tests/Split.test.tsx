import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { Split } from "../src/components/Split";

describe("Split", () => {
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

  it("pone el frame antes que la columna", async () => {
    await act(async () => {
      root.render(<Split main={<p>Frame</p>} side={<p>Notas</p>} />);
    });

    const text = container.textContent ?? "";
    expect(text.indexOf("Frame")).toBeGreaterThanOrEqual(0);
    expect(text.indexOf("Frame")).toBeLessThan(text.indexOf("Notas"));
  });

  it("muestra solo la columna cuando no hay frame", async () => {
    await act(async () => {
      root.render(<Split side={<p>Notas</p>} />);
    });

    expect(container.textContent).toContain("Notas");
    expect(container.textContent).not.toContain("Frame");
  });
});
