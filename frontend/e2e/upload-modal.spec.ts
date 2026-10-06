import { expect, test } from "@playwright/test";

test("nuevo análisis: dos columnas, archivo, arrastre, cancelación y diseño móvil", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.emulateMedia({ colorScheme: "light" });
  await page.route("**/sessions", route => route.fulfill({ json: [] }));
  await page.route("**/processed-sessions", route => route.fulfill({ json: [] }));
  await page.route("**/cameras", route => route.fulfill({ json: [{ id: "camera-1", name: "Entrada principal", created_at: "2026-10-05T00:00:00Z" }] }));
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await page.getByRole("button", { name: "Nuevo análisis", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Nuevo análisis" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText("Cargá el video de tu cámara fija y asigná la ubicación para comenzar.")).toBeVisible();
  const width = (await dialog.boundingBox())!.width;
  expect(width).toBeGreaterThanOrEqual(880);
  expect(width).toBeLessThanOrEqual(920);
  const drop = dialog.getByRole("group", { name: "Soltar archivo de video" });
  const name = dialog.getByRole("textbox", { name: "Nombre de la sesión" });
  expect((await name.boundingBox())!.x).toBeGreaterThan((await drop.boundingBox())!.x + (await drop.boundingBox())!.width);
  await page.screenshot({ path: "test-results/upload-modal-light.png", fullPage: true });
  await dialog.getByLabel("Archivo de video", { exact: true }).setInputFiles({ name: "entrada.mp4", mimeType: "video/mp4", buffer: Buffer.from("video") });
  await expect(dialog.getByText("entrada.mp4", { exact: true })).toBeVisible();
  await name.fill("Entrada - Mañana");
  await dialog.getByRole("combobox", { name: "Cámara asignada" }).selectOption("camera-1");
  await expect(dialog.getByRole("button", { name: "Registrar video" })).toBeEnabled();
  await dialog.getByRole("button", { name: "Quitar archivo" }).click();
  await expect(dialog.getByRole("button", { name: "Registrar video" })).toBeDisabled();
  const dataTransfer = await page.evaluateHandle(() => {
    const data = new DataTransfer();
    data.items.add(new File(["video"], "arrastrado.mp4", { type: "video/mp4" }));
    return data;
  });
  await drop.dispatchEvent("drop", { dataTransfer });
  await expect(dialog.getByText("arrastrado.mp4", { exact: true })).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Registrar video" })).toBeEnabled();
  await dataTransfer.dispose();
  await dialog.getByRole("button", { name: "Cancelar" }).click();
  await expect(dialog).not.toBeVisible();
  await page.getByRole("button", { name: "Activar modo oscuro" }).click();
  await page.getByRole("button", { name: "Nuevo análisis", exact: true }).click();
  await expect(dialog).toHaveCSS("background-color", "rgb(29, 30, 34)");
  await expect(dialog).toHaveCSS("border-top-color", "rgb(65, 68, 72)");
  await expect(drop).toHaveCSS("background-color", "rgb(39, 43, 46)");
  await expect(name).toHaveCSS("background-color", "rgb(29, 30, 34)");
  const homeAction = page.getByRole("button", { name: "Nuevo análisis", exact: true });
  await expect(dialog.getByRole("button", { name: "Registrar video" })).toHaveCSS(
    "background-color", await homeAction.evaluate(element => getComputedStyle(element).backgroundColor),
  );
  await page.screenshot({ path: "test-results/upload-modal-dark.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(async () => (await name.boundingBox())!.y > (await drop.boundingBox())!.y + (await drop.boundingBox())!.height).toBe(true);
  expect(await dialog.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true);
  await page.screenshot({ path: "test-results/upload-modal-mobile.png", fullPage: true });
  await dialog.getByRole("button", { name: "Cerrar" }).click();
  expect(errors).toEqual([]);
});
