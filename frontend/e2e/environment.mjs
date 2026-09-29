// Entorno compartido por el runner e2e (Node puro) y por el soporte de Playwright.
// Las variables ya presentes en el entorno del proceso ganan; el `.env` solo completa las que faltan.
import fs from "node:fs";
import path from "node:path";

export const AZURE_HOST_SUFFIX = ".postgres.database.azure.com";

export function parseEnvironmentFile(text) {
  const values = {};
  for (const line of text.split(/\r?\n/)) {
    const separator = line.indexOf("=");
    if (separator > 0 && !line.trimStart().startsWith("#")) {
      values[line.slice(0, separator).trim()] = line.slice(separator + 1).trim();
    }
  }
  return values;
}

export function mergeEnvironment(base, environmentFileText) {
  const values = { ...base };
  for (const [name, value] of Object.entries(parseEnvironmentFile(environmentFileText))) {
    if (values[name] === undefined) {
      values[name] = value;
    }
  }
  return values;
}

export function databaseHost(databaseUrl) {
  // Los mensajes nunca incluyen la URL: puede contener credenciales.
  if (databaseUrl === undefined || databaseUrl.trim() === "") {
    throw new Error("FLOWSIGHT_DATABASE_URL no está configurada para el e2e.");
  }
  let host;
  try {
    host = new URL(databaseUrl.trim()).hostname;
  } catch {
    throw new Error("FLOWSIGHT_DATABASE_URL no es una URL válida.");
  }
  if (!host) {
    throw new Error("FLOWSIGHT_DATABASE_URL no tiene un host válido.");
  }
  return host.toLowerCase().replace(/\.+$/, "");
}

export function isAzureHost(host) {
  return host.endsWith(AZURE_HOST_SUFFIX);
}

export function assertSafeDatabase(environment) {
  const host = databaseHost(environment.FLOWSIGHT_DATABASE_URL);
  if (isAzureHost(host)) {
    throw new Error(
      "FLOWSIGHT_DATABASE_URL apunta a la base compartida de Azure; el e2e migra y escribe datos " +
        "y nunca corre ahí. Exportá FLOWSIGHT_DATABASE_URL con un PostgreSQL local o de pruebas.",
    );
  }
  return host;
}

// Igual que `destructive_database_url` del backend: si hay base de pruebas, el e2e usa esa.
export function preferTestDatabase(environment) {
  const testUrl = environment.FLOWSIGHT_TEST_DATABASE_URL?.trim();
  if (!testUrl) {
    return environment;
  }
  return { ...environment, FLOWSIGHT_DATABASE_URL: testUrl };
}

export function loadLocalEnvironment(root, base = process.env) {
  const environmentFile = path.join(root, ".env");
  const text = fs.existsSync(environmentFile) ? fs.readFileSync(environmentFile, "utf8") : "";
  return preferTestDatabase(mergeEnvironment(base, text));
}
