import { describe, expect, it } from "vitest";

import { sequenceLabel } from "../src/presentation/sequenceLabel";
import type { AreaRef } from "../src/api/visitPatterns";

const zones = [
  { id: "z1", name: "Zona 1" },
  { id: "z2", name: "Zona 2" },
];

function area(shop: string, role: AreaRef["zone_role"]): AreaRef {
  return { shop_id: shop, zone_role: role };
}

describe("sequenceLabel", () => {
  it("nombra un área sola con el número de la zona", () => {
    expect(sequenceLabel([area("z1", "front")], zones)).toBe("Frente1");
    expect(sequenceLabel([area("z1", "interior")], zones)).toBe("Interior1");
    expect(sequenceLabel([area("z1", "window")], zones)).toBe("Vidriera1");
  });

  it("usa una flecha cuando el recorrido va en un solo sentido", () => {
    expect(sequenceLabel([area("z1", "front"), area("z1", "interior")], zones)).toBe("Frente1 → Interior1");
    expect(sequenceLabel([area("z1", "interior"), area("z1", "front")], zones)).toBe("Interior1 → Frente1");
  });

  it("abrevia la ida y vuelta y cuenta las idas desde la segunda", () => {
    const frente = area("z1", "front");
    const interior = area("z1", "interior");
    expect(sequenceLabel([frente, interior, frente], zones)).toBe("Frente1 ⇄ Interior1");
    expect(sequenceLabel([frente, interior, frente, interior], zones)).toBe("Frente1 ⇄ Interior1 (X2)");
    expect(sequenceLabel([frente, interior, frente, interior, frente], zones)).toBe("Frente1 ⇄ Interior1 (X2)");
    expect(sequenceLabel([frente, interior, frente, interior, frente, interior], zones)).toBe(
      "Frente1 ⇄ Interior1 (X3)",
    );
  });

  it("no abrevia un recorrido que entra en una tercera área", () => {
    expect(
      sequenceLabel([area("z1", "front"), area("z1", "interior"), area("z2", "front")], zones),
    ).toBe("Frente1 → Interior1 → Frente2");
  });

  it("usa el nombre completo si no termina en un número", () => {
    expect(sequenceLabel([area("k", "front")], [{ id: "k", name: "Kiosco" }])).toBe("Frente Kiosco");
  });

  it("usa solo el rol si la zona no está en el resultado", () => {
    expect(sequenceLabel([area("missing", "front")], [])).toBe("Frente");
  });
});
