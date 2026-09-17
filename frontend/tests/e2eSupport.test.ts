import path from "node:path";
import { describe, expect, it } from "vitest";

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
