import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { PositionHeatmap } from "../src/components/PositionHeatmap";

describe("PositionHeatmap", () => {
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

  it("dibuja los pies y explica el vacío sin ocupar el lugar de los indicadores", async () => {
    await act(async () =>
      root.render(
        <PositionHeatmap availability="available" samples={[{ foot: [0.2, 0.8] }]} />,
      ),
    );
    expect(container.querySelector("circle")).not.toBeNull();

    await act(async () => root.render(<PositionHeatmap availability="unavailable" samples={[]} />));
    expect(container.textContent).toContain("No hay muestra de posiciones en este equipo.");
    expect(container.querySelector("circle")).toBeNull();
  });
});
