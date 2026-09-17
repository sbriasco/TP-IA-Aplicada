import { spawn, spawnSync, type ChildProcess } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

export function resolveWorkerExecutable(root: string, platform: NodeJS.Platform): string {
  const parts =
    platform === "win32"
      ? ["backend", ".venv", "Scripts", "python.exe"]
      : ["backend", ".venv", "bin", "python"];
  return path.join(root, ...parts);
}

export function localEnvironment(root: string): NodeJS.ProcessEnv {
  const values: NodeJS.ProcessEnv = { ...process.env };
  const environmentFile = path.join(root, ".env");
  const lines = fs.existsSync(environmentFile)
    ? fs.readFileSync(environmentFile, "utf8").split(/\r?\n/)
    : [];
  for (const line of lines) {
    const separator = line.indexOf("=");
    if (separator > 0 && !line.trimStart().startsWith("#")) {
      values[line.slice(0, separator).trim()] = line.slice(separator + 1).trim();
    }
  }
  return values;
}

export function startWorker(root: string): ChildProcess {
  return spawn(resolveWorkerExecutable(root, process.platform), ["-m", "flowsight.worker.main"], {
    cwd: path.join(root, "backend"),
    env: localEnvironment(root),
    stdio: "ignore",
  });
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
  worker.kill("SIGTERM");
}
