import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  // El worker reclama cualquier análisis pendiente. En paralelo una prueba se queda con el trabajo de otra.
  workers: 1,
  reporter: "list",
  use: { baseURL: process.env.FLOWSIGHT_E2E_BASE_URL ?? "http://127.0.0.1:5173" },
});
