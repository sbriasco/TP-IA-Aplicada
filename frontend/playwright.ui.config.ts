import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testMatch: ["live-statistics.spec.ts", "dashboard.spec.ts", "upload-modal.spec.ts", "scene-workspace.spec.ts"],
  workers: 1,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:5181",
    channel: process.env.FLOWSIGHT_E2E_BROWSER_CHANNEL === "chrome" ? "chrome" : undefined,
  },
  webServer: {
    command: "node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5181 --strictPort",
    url: "http://127.0.0.1:5181",
    reuseExistingServer: true,
  },
});
