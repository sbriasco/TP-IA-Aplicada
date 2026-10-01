import net from "node:net";
import { describe, expect, it } from "vitest";
import { assertPortAvailable } from "../e2e/ports.mjs";

describe("aislamiento del runner e2e", () => {
  it("rechaza un puerto ocupado para no ejecutar pruebas contra otro servicio", async () => {
    const server = net.createServer();
    await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
    try {
      const address = server.address() as net.AddressInfo;
      await expect(assertPortAvailable(address.port)).rejects.toThrow("ocupado");
    } finally { await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve())); }
  });
});
