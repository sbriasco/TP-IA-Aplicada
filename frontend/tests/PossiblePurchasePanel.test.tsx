import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { PossiblePurchasePanel } from "../src/components/PossiblePurchasePanel";
import type { PossiblePurchases } from "../src/api/possiblePurchases";

function sample(overrides: Partial<PossiblePurchases> = {}): PossiblePurchases {
  return {
    availability: "available",
    visit_count: 2,
    minimum_seconds: "1",
    precision_uncommitted: true,
    track_ids: [1, 3],
    ...overrides,
  };
}

describe("PossiblePurchasePanel", () => {
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

  it("muestra cantidad, umbral, estimación y aviso de precisión", async () => {
    await act(async () => {
      root.render(<PossiblePurchasePanel purchases={sample()} />);
    });
    const text = container.textContent ?? "";
    expect(text).toContain("2 visitas con posible compra estimada");
    expect(text).toContain("1 segundo");
    expect(text).toContain("estimación");
    expect(text).toContain("no es una venta confirmada");
    expect(text).toContain("La precisión de la posible compra estimada no está comprometida.");
  });

  it("cero visitas se lee como cero disponible", async () => {
    await act(async () => {
      root.render(<PossiblePurchasePanel purchases={sample({ visit_count: 0, track_ids: [] })} />);
    });
    expect(container.textContent).toContain("0 visitas con posible compra estimada");
  });
});
