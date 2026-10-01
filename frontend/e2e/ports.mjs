import net from "node:net";

export function assertPortAvailable(port) {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once("error", () => reject(new Error(`El puerto ${port} está ocupado o no se puede abrir; el e2e no usará un servicio existente.`)));
    server.listen(port, "127.0.0.1", () => server.close((error) => error ? reject(error) : resolve()));
  });
}
