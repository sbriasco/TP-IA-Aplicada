import { spawn, spawnSync, type ChildProcess } from "node:child_process";
import path from "node:path";

import { assertSafeDatabase, loadLocalEnvironment } from "./environment.mjs";

export function resolveWorkerExecutable(root: string, platform: NodeJS.Platform): string {
  const parts =
    platform === "win32"
      ? ["backend", ".venv", "Scripts", "python.exe"]
      : ["backend", ".venv", "bin", "python"];
  return path.join(root, ...parts);
}

export function localEnvironment(root: string): NodeJS.ProcessEnv {
  const values = loadLocalEnvironment(root, process.env);
  assertSafeDatabase(values);
  return values;
}

export function startWorker(root: string, captureDiagnostics = false, overrides: NodeJS.ProcessEnv = {}): ChildProcess {
  const worker = spawn(resolveWorkerExecutable(root, process.platform), ["-m", "flowsight.worker.main"], {
    cwd: path.join(root, "backend"),
    env: { ...localEnvironment(root), ...overrides },
    stdio: captureDiagnostics ? ["ignore", "ignore", "pipe"] : "ignore",
    windowsHide: true,
  });
  if (captureDiagnostics) worker.stderr?.on("data", (chunk: Buffer) => {
    for (const line of chunk.toString().split(/\r?\n/)) {
      if (line.startsWith("INFO:flowsight.capture:")) console.log(line);
    }
  });
  return worker;
}

function pause(milliseconds: number): void {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, milliseconds);
}

function processIsRunning(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

export function stopWorker(worker: ChildProcess): void {
  if (worker.pid === undefined) {
    return;
  }
  if (process.platform === "win32") {
    const command = [
      `$ids = @(${worker.pid})`,
      "do {",
      "$children = @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.Parent -and $ids -contains $_.Parent.Id -and $ids -notcontains $_.Id })",
      "$ids += @($children.Id)",
      "} while ($children.Count -gt 0)",
      "$ids | Sort-Object -Descending | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }",
    ].join("; ");
    spawnSync("powershell.exe", ["-NoProfile", "-Command", command], { stdio: "ignore" });
    return;
  }
  // The machine lease is a Postgres advisory lock. The next test's worker exits
  // if this process is still holding it, and then nobody publishes the preview.
  worker.kill("SIGTERM");
  const deadline = Date.now() + 5_000;
  while (processIsRunning(worker.pid) && Date.now() < deadline) {
    pause(50);
  }
  if (processIsRunning(worker.pid)) {
    worker.kill("SIGKILL");
    const forced = Date.now() + 1_000;
    while (processIsRunning(worker.pid) && Date.now() < forced) {
      pause(50);
    }
  }
}
