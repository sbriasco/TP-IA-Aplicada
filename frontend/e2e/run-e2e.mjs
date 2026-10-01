import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { assertSafeDatabase, loadLocalEnvironment } from "./environment.mjs";

const currentDirectory = path.dirname(fileURLToPath(import.meta.url));
const frontend = path.resolve(currentDirectory, "..");
const root = path.resolve(frontend, "..");
const backend = path.join(root, "backend");
const environment = loadLocalEnvironment(root, process.env);

// Antes de migrar o arrancar procesos: nunca contra la base compartida de Azure.
try {
  const host = assertSafeDatabase(environment);
  console.log(`e2e: usando PostgreSQL en ${host}`);
} catch (error) {
  console.error(`e2e abortado: ${error instanceof Error ? error.message : String(error)}`);
  process.exit(2);
}

const executableDirectory = process.platform === "win32" ? "Scripts" : "bin";
const executableSuffix = process.platform === "win32" ? ".exe" : "";
const python = path.join(backend, ".venv", executableDirectory, `python${executableSuffix}`);
const alembic = path.join(backend, ".venv", executableDirectory, `alembic${executableSuffix}`);

function run(command, args, cwd) {
  return spawn(command, args, { cwd, env: environment, stdio: "inherit", windowsHide: true });
}

function stopTree(child) {
  if (child.pid === undefined || child.exitCode !== null) {
    return;
  }
  if (process.platform === "win32") {
    const command = [
      `$ids = @(${child.pid})`,
      "do {",
      "$children = @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.Parent -and $ids -contains $_.Parent.Id -and $ids -notcontains $_.Id })",
      "$ids += @($children.Id)",
      "} while ($children.Count -gt 0)",
      "$ids | Sort-Object -Descending | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }",
    ].join("; ");
    spawnSync("powershell.exe", ["-NoProfile", "-Command", command], { stdio: "ignore" });
  } else {
    child.kill("SIGTERM");
  }
}

async function waitFor(url) {
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) {
        return;
      }
    } catch {
      // El componente todavía está iniciando.
    }
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error(`El servicio no respondió a tiempo: ${url}`);
}

// Videos registrados y clip de prueba en directorios temporales: el e2e no toca los de la máquina.
const videosDirectory = fs.mkdtempSync(path.join(os.tmpdir(), "flowsight-e2e-videos-"));
const clipDirectory = fs.mkdtempSync(path.join(os.tmpdir(), "flowsight-e2e-clip-"));
function removeTemporaryDirectories() {
  fs.rmSync(videosDirectory, { recursive: true, force: true });
  fs.rmSync(clipDirectory, { recursive: true, force: true });
}
environment.FLOWSIGHT_VIDEOS_DIR = videosDirectory;
environment.FLOWSIGHT_MACHINE_ID = "e2e-ci";
environment.FLOWSIGHT_CHAT_FAKE_DRAFTER = "1";

const clip = spawnSync(python, ["-m", "flowsight.video.fixtures", clipDirectory, "--size", "1280x720"], {
  cwd: backend,
  env: environment,
  encoding: "utf8",
});
if (clip.status !== 0) {
  removeTemporaryDirectories();
  throw new Error(`No se pudo generar el clip de prueba: ${clip.stderr}`);
}
environment.FLOWSIGHT_E2E_CLIP = clip.stdout.trim();

const migration = spawnSync(alembic, ["upgrade", "head"], {
  cwd: backend,
  env: environment,
  stdio: "inherit",
});
if (migration.status !== 0) {
  removeTemporaryDirectories();
  throw new Error("No se pudieron aplicar las migraciones para Playwright.");
}

let result;
let api;
let vite;
try {
  api = run(
    python,
    ["-m", "uvicorn", "flowsight.api.main:create_app", "--factory", "--host", "127.0.0.1", "--port", "8000"],
    backend,
  );
  const viteCli = path.join(frontend, "node_modules", "vite", "bin", "vite.js");
  vite = run(process.execPath, [viteCli, "--host", "127.0.0.1"], frontend);
  await Promise.all([
    waitFor("http://127.0.0.1:8000/health"),
    waitFor("http://127.0.0.1:5173"),
  ]);
  const playwrightCli = path.join(frontend, "node_modules", "@playwright", "test", "cli.js");
  result = spawnSync(process.execPath, [playwrightCli, "test"], {
    cwd: frontend,
    env: environment,
    stdio: "inherit",
  });
} finally {
  if (vite !== undefined) {
    stopTree(vite);
  }
  if (api !== undefined) {
    stopTree(api);
  }
  removeTemporaryDirectories();
}

process.exit(result?.status ?? 1);
