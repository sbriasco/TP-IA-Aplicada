import { expect, test } from "@playwright/test";

const API = process.env.FLOWSIGHT_E2E_API_URL ?? "http://127.0.0.1:8000";

test("el historial permite cancelar y confirmar la eliminación de una sesión", async ({ page, request }) => {
  const name = "Eliminar e2e " + Date.now();
  const response = await request.post(API + "/sessions", { data: { name, camera_id: name } });
  expect(response.ok()).toBeTruthy();
  const session = await response.json() as { id: string };
  await page.setViewportSize({ width: 1024, height: 768 });
  await page.goto("/");
  const row = page.getByRole("row").filter({ has: page.getByRole("link", { name, exact: true }) });
  await expect(row).toHaveCount(1);
  await expect(row.getByText("Sin analizar", { exact: true })).toBeVisible();
  await row.getByRole("button", { name: "Eliminar " + name }).click();
  const dialog = page.getByRole("dialog", { name: "Eliminar análisis", exact: true });
  await dialog.getByRole("button", { name: "Cancelar" }).click();
  expect((await request.get(API + "/sessions/" + session.id)).ok()).toBeTruthy();
  await expect(row).toHaveCount(1);
  await row.getByRole("button", { name: "Eliminar " + name }).click();
  await dialog.getByRole("button", { name: "Eliminar del historial", exact: true }).click();
  await expect(row).toHaveCount(0);
  expect((await request.get(API + "/sessions/" + session.id)).status()).toBe(404);
  await page.reload();
  await expect(row).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
});
