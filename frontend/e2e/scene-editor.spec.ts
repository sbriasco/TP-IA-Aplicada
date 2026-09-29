import { expect, test, type Locator, type Page } from "@playwright/test";

const API = "http://127.0.0.1:8000";
const WIDTH = 1280;
const HEIGHT = 720;

type Point = [number, number];

type SceneVersionSummary = { id: string; version_number: number };
type SceneVersionDetail = {
  created_by_machine_id: string | null;
  frame_width: number;
  frame_height: number;
  shops: {
    name: string;
    zones: Partial<Record<"front" | "interior" | "showcase", Point[]>>;
    entry_line: { start: Point; end: Point; entry_direction: "a_to_b" | "b_to_a" };
  }[];
};

function frameCanvas(page: Page): Locator {
  return page.getByRole("group", { name: "Frame de referencia con la escena" });
}

/** Punto del frame (px) a coordenadas de pantalla con la matriz del SVG, como hace el editor. */
async function toScreen(page: Page, [x, y]: Point): Promise<Point> {
  return frameCanvas(page).evaluate(
    (element, [px, py]) => {
      const matrix = (element as SVGSVGElement).getScreenCTM();
      if (matrix === null) throw new Error("El lienzo no tiene matriz de pantalla.");
      return [matrix.a * px + matrix.c * py + matrix.e, matrix.b * px + matrix.d * py + matrix.f];
    },
    [x, y] as Point,
  );
}

async function clickFrame(page: Page, point: Point): Promise<void> {
  const [x, y] = await toScreen(page, point);
  await page.mouse.click(x, y);
}

async function drawZone(page: Page, role: "front" | "interior" | "showcase", points: Point[]): Promise<void> {
  await page.getByLabel("Rol de la zona nueva").selectOption(role);
  await page.getByRole("button", { name: "Crear zona" }).click();
  for (const point of points) await clickFrame(page, point);
  await page.getByRole("button", { name: "Cerrar polígono" }).click();
}

async function vertexCenter(vertex: Locator): Promise<Point> {
  return [Number(await vertex.getAttribute("cx")), Number(await vertex.getAttribute("cy"))];
}

/** Vértices dibujados de un elemento, en píxeles del frame, leídos del SVG. */
async function drawnVertices(page: Page, elementName: string, shopName: string): Promise<Point[]> {
  const vertices = page.getByRole("button", {
    name: new RegExp(`^Vértice \\d+ de ${elementName} de ${shopName}$`),
  });
  const points: Point[] = [];
  for (let index = 1; index <= (await vertices.count()); index += 1) {
    points.push(
      await vertexCenter(
        page.getByRole("button", { name: `Vértice ${index} de ${elementName} de ${shopName}` }),
      ),
    );
  }
  return points;
}

function expectSamePoints(saved: Point[] | undefined, drawn: Point[]): void {
  expect(saved).toBeDefined();
  expect(saved).toHaveLength(drawn.length);
  saved!.forEach(([x, y], index) => {
    // SC-004: la versión guardada coincide con lo dibujado dentro del 0,5 % del ancho y del alto.
    expect(Math.abs(x * WIDTH - drawn[index][0])).toBeLessThan(WIDTH * 0.005);
    expect(Math.abs(y * HEIGHT - drawn[index][1])).toBeLessThan(HEIGHT * 0.005);
  });
}

test("configura la escena de una sesión de video desde el editor", async ({ page, request }) => {
  const clipPath = process.env.FLOWSIGHT_E2E_CLIP;
  if (clipPath === undefined || clipPath === "") {
    throw new Error("Falta FLOWSIGHT_E2E_CLIP: correr con `npm run test:e2e`.");
  }
  // Cámara nueva en cada corrida, para que el editor no precargue versiones de corridas anteriores.
  const cameraName = `e2e-escena-${Date.now()}`;
  const sessionName = `E2E escena ${Date.now()}`;
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.setViewportSize({ width: 1400, height: 1000 });

  await test.step("registra el clip desde la pantalla de sesiones", async () => {
    await page.goto("/");
    await page.getByLabel("Archivo de video").setInputFiles(clipPath);
    await page.getByLabel("Nombre de la sesión").fill(sessionName);
    await page.getByLabel("Nombre de la cámara").fill(cameraName);
    await page.getByRole("button", { name: "Crear cámara" }).click();
    await expect(page.getByRole("status").filter({ hasText: cameraName })).toBeVisible();
    await page.getByRole("button", { name: "Registrar video" }).click();
    await page.waitForURL(/\/sessions\/[^/]+$/);
  });

  const sessionId = decodeURIComponent(new URL(page.url()).pathname.split("/").at(-1)!);
  const sessionResponse = await request.get(`${API}/sessions/${sessionId}`);
  expect(sessionResponse.ok()).toBeTruthy();
  const cameraId = ((await sessionResponse.json()) as { camera: { id: string } }).camera.id;

  await test.step("muestra el frame de referencia y abre el editor", async () => {
    const frame = page.getByRole("img", { name: `Frame de referencia de ${sessionName}` });
    await expect(frame).toBeVisible();
    await expect.poll(() => frame.evaluate((image) => (image as HTMLImageElement).naturalWidth)).toBe(WIDTH);
    await page.getByRole("link", { name: "Editar escena" }).click();
    await page.waitForURL(/\/editor$/);
    await expect(frameCanvas(page)).toBeVisible();
  });

  await test.step("dibuja Local A con sus tres zonas y la línea de entrada", async () => {
    await page.getByRole("button", { name: "Agregar local" }).click();
    await page.getByLabel("Nombre del local").fill("Local A");
    await drawZone(page, "front", [[200, 400], [500, 400], [500, 550], [200, 550]]);
    await drawZone(page, "interior", [[200, 100], [500, 100], [500, 380], [200, 380]]);
    await drawZone(page, "showcase", [[520, 400], [620, 400], [620, 550]]);
    await page.getByRole("button", { name: "Crear línea de entrada" }).click();
    await clickFrame(page, [200, 600]);
    await clickFrame(page, [500, 600]);

    await expect(page.getByRole("img", { name: "Lado A de Local A" })).toBeVisible();
    await expect(page.getByRole("img", { name: "Lado B de Local A" })).toBeVisible();
    // Con la línea horizontal la flecha es vertical: su caja mide 0 de ancho y Playwright la
    // considera oculta aunque se ve; alcanza con que exista con el sentido correcto.
    await expect(page.getByRole("img", { name: "Flecha de entrada de Local A: de A a B" })).toBeAttached();
    await page.getByLabel("B → A es entrada").check();
    await expect(page.getByRole("img", { name: "Flecha de entrada de Local A: de B a A" })).toBeAttached();
    await page.getByLabel("A → B es entrada").check();
    await expect(page.getByRole("img", { name: "Flecha de entrada de Local A: de A a B" })).toBeAttached();
  });

  const firstVertex = page.getByRole("button", { name: "Vértice 1 de zona frontal de Local A" });

  await test.step("mueve un vértice con el teclado", async () => {
    const [x0, y0] = await vertexCenter(firstVertex);
    await firstVertex.focus();
    await page.keyboard.press("ArrowRight");
    await page.keyboard.press("Shift+ArrowDown");
    const [x1, y1] = await vertexCenter(firstVertex);
    expect(x1 - x0).toBeCloseTo(1);
    expect(y1 - y0).toBeCloseTo(10);
  });

  await test.step("mantiene los vértices sobre la imagen al redimensionar", async () => {
    const framePoint = await vertexCenter(firstVertex);
    for (const size of [
      { width: 900, height: 700 },
      { width: 1600, height: 900 },
      { width: 700, height: 1000 },
    ]) {
      await page.setViewportSize(size);
      const box = await firstVertex.boundingBox();
      expect(box).not.toBeNull();
      const [x, y] = await toScreen(page, framePoint);
      expect(Math.abs(box!.x + box!.width / 2 - x)).toBeLessThan(1.5);
      expect(Math.abs(box!.y + box!.height / 2 - y)).toBeLessThan(1.5);
    }
    await page.setViewportSize({ width: 1400, height: 1000 });
  });

  await test.step("guarda la versión igual a lo dibujado", async () => {
    await page.getByRole("button", { name: "Guardar versión" }).click();
    await expect(page.getByRole("status").filter({ hasText: /Se guardó la versión \d+\./ })).toBeVisible();

    const listResponse = await request.get(`${API}/cameras/${cameraId}/scene-versions`);
    expect(listResponse.ok()).toBeTruthy();
    const versions = (await listResponse.json()) as SceneVersionSummary[];
    expect(versions).toHaveLength(1);
    const detailResponse = await request.get(`${API}/scene-versions/${versions[0].id}`);
    expect(detailResponse.ok()).toBeTruthy();
    const saved = (await detailResponse.json()) as SceneVersionDetail;

    expect(saved.created_by_machine_id).toBe("e2e-ci");
    expect([saved.frame_width, saved.frame_height]).toEqual([WIDTH, HEIGHT]);
    expect(saved.shops).toHaveLength(1);
    const [shop] = saved.shops;
    expect(shop.name).toBe("Local A");
    expectSamePoints(shop.zones.front, await drawnVertices(page, "zona frontal", "Local A"));
    expectSamePoints(shop.zones.interior, await drawnVertices(page, "zona interior", "Local A"));
    expectSamePoints(shop.zones.showcase, await drawnVertices(page, "zona de vidriera", "Local A"));
    expectSamePoints(
      [shop.entry_line.start, shop.entry_line.end],
      await drawnVertices(page, "línea de entrada", "Local A"),
    );
    expect(shop.entry_line.entry_direction).toBe("a_to_b");
  });

  await test.step("marca un polígono autointersectado sin perder el dibujo", async () => {
    await page.getByRole("button", { name: "Agregar local" }).click();
    await page.getByLabel("Nombre del local").fill("Local B");
    await drawZone(page, "front", [[800, 100], [1000, 300], [1000, 100], [800, 300]]);
    await page.getByRole("button", { name: "Crear línea de entrada" }).click();
    await clickFrame(page, [800, 600]);
    await clickFrame(page, [1000, 600]);
    await page.getByRole("button", { name: "Guardar versión" }).click();

    await expect(page.getByRole("alert").filter({ hasText: /No se guardó la versión/ })).toBeVisible();
    await expect(page.getByRole("group", { name: "Zona frontal de Local B" })).toHaveAttribute(
      "aria-invalid",
      "true",
    );
    await expect(page.getByRole("button", { name: /^Vértice \d+ de zona frontal de Local B$/ })).toHaveCount(4);
    const versions = (await (await request.get(`${API}/cameras/${cameraId}/scene-versions`)).json()) as unknown[];
    expect(versions).toHaveLength(1);
  });

  await test.step("advierte antes de salir con cambios sin guardar", async () => {
    const back = page.getByRole("link", { name: "Volver a la sesión" });
    const dismissed = page.waitForEvent("dialog").then((dialog) => dialog.dismiss());
    await back.click();
    await dismissed;
    await expect(page).toHaveURL(/\/editor$/);

    const accepted = page.waitForEvent("dialog").then((dialog) => dialog.accept());
    await back.click();
    await accepted;
    await page.waitForURL(new RegExp(`/sessions/${sessionId}$`));
  });

  expect(errors).toEqual([]);
});
