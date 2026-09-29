import path from "node:path";
import { describe, expect, it } from "vitest";

import {
  assertSafeDatabase,
  databaseHost,
  mergeEnvironment,
  parseEnvironmentFile,
  preferTestDatabase,
} from "../e2e/environment.mjs";
import { resolveWorkerExecutable } from "../e2e/support";

describe("resolveWorkerExecutable", () => {
  it("usa Scripts/python.exe en Windows", () => {
    expect(resolveWorkerExecutable("repo", "win32")).toBe(
      path.join("repo", "backend", ".venv", "Scripts", "python.exe"),
    );
  });

  it("usa bin/python en Linux", () => {
    expect(resolveWorkerExecutable("repo", "linux")).toBe(
      path.join("repo", "backend", ".venv", "bin", "python"),
    );
  });
});

describe("entorno del e2e", () => {
  const envText = [
    "# comentario=ignorado",
    "   # FLOWSIGHT_ENV=comentado",
    "LINEA_SIN_IGUAL",
    "=sin_nombre",
    "FLOWSIGHT_DATABASE_URL=postgresql+psycopg://u:p@shared.postgres.database.azure.com:5432/db",
    "FLOWSIGHT_WORKER_ID = worker-env ",
    "FLOWSIGHT_API_PORT=9000",
  ].join("\n");

  it("process.env gana sobre el .env", () => {
    const merged = mergeEnvironment(
      { FLOWSIGHT_DATABASE_URL: "postgresql+psycopg://u:p@127.0.0.1:5433/test", FLOWSIGHT_API_PORT: "8000" },
      envText,
    );
    expect(merged.FLOWSIGHT_DATABASE_URL).toBe("postgresql+psycopg://u:p@127.0.0.1:5433/test");
    expect(merged.FLOWSIGHT_API_PORT).toBe("8000");
  });

  it("el .env completa las variables que faltan", () => {
    const merged = mergeEnvironment({}, envText);
    expect(merged.FLOWSIGHT_WORKER_ID).toBe("worker-env");
    expect(merged.FLOWSIGHT_API_PORT).toBe("9000");
  });

  it("ignora comentarios y líneas sin =", () => {
    expect(parseEnvironmentFile(envText)).toEqual({
      FLOWSIGHT_DATABASE_URL: "postgresql+psycopg://u:p@shared.postgres.database.azure.com:5432/db",
      FLOWSIGHT_WORKER_ID: "worker-env",
      FLOWSIGHT_API_PORT: "9000",
    });
  });

  it("bloquea un host de Azure, sin importar mayúsculas", () => {
    expect(() =>
      assertSafeDatabase({
        FLOWSIGHT_DATABASE_URL: "postgresql+psycopg://x:y@Demo.Postgres.Database.Azure.com:5432/db",
      }),
    ).toThrow(/Azure/);
  });

  it("bloquea Azure aunque venga solo del .env", () => {
    expect(() => assertSafeDatabase(mergeEnvironment({}, envText))).toThrow(/Azure/);
  });

  it("deja pasar un host local", () => {
    expect(
      assertSafeDatabase({ FLOWSIGHT_DATABASE_URL: "postgresql+psycopg://u:p@127.0.0.1:5433/test" }),
    ).toBe("127.0.0.1");
  });

  it("una URL inválida da un error claro sin mostrar la URL", () => {
    expect(() => databaseHost("no-es-una-url-secreta")).toThrow(
      "FLOWSIGHT_DATABASE_URL no es una URL válida.",
    );
    expect(() => databaseHost("postgresql+psycopg:///db")).toThrow(/host válido/);
    expect(() => databaseHost(undefined)).toThrow(/no está configurada/);
  });
});

describe("preferTestDatabase", () => {
  const shared = "postgresql+psycopg://u:p@demo.postgres.database.azure.com:5432/db";
  const local = "postgresql+psycopg://u:p@127.0.0.1:5433/flowsight_test";

  it("usa FLOWSIGHT_TEST_DATABASE_URL como base del e2e", () => {
    const environment = preferTestDatabase({
      FLOWSIGHT_DATABASE_URL: shared,
      FLOWSIGHT_TEST_DATABASE_URL: local,
    });

    expect(environment.FLOWSIGHT_DATABASE_URL).toBe(local);
    expect(assertSafeDatabase(environment)).toBe("127.0.0.1");
  });

  it("sin base de pruebas deja FLOWSIGHT_DATABASE_URL como está", () => {
    const base = { FLOWSIGHT_DATABASE_URL: local, FLOWSIGHT_TEST_DATABASE_URL: "  " };

    expect(preferTestDatabase(base)).toBe(base);
  });

  it("sigue bloqueando si la base de pruebas es de Azure", () => {
    const environment = preferTestDatabase({ FLOWSIGHT_TEST_DATABASE_URL: shared });

    expect(() => assertSafeDatabase(environment)).toThrow(/Azure/);
  });
});
