import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  // Estas pantallas mockean la API. Corren con `npm run test:e2e:ui`, sin PostgreSQL ni worker.
  testIgnore: [
    "dashboard.spec.ts",
    "live-results.spec.ts",
    "live-statistics.spec.ts",
    "results-dashboard.spec.ts",
    "scene-workspace.spec.ts",
    "upload-modal.spec.ts",
    "video-preparation.spec.ts",
  ],
  // El worker reclama cualquier análisis pendiente. En paralelo una prueba se queda con el trabajo de otra.
  workers: 1,
  reporter: "list",
  use: { baseURL: process.env.FLOWSIGHT_E2E_BASE_URL ?? "http://127.0.0.1:5173" },
});
