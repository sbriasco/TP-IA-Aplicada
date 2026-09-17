import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { startWorker, stopWorker } from "./support";

const currentDirectory = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(currentDirectory, "../..");

type PreviewMessage = {
  type: "preview.update" | "job.terminal";
  frame_index?: number;
  status?: string;
};

async function createJob(request: APIRequestContext): Promise<string> {
  const sessionResponse = await request.post("http://127.0.0.1:8000/sessions", {
    data: { name: "E2E", camera_id: "camera-e2e" },
  });
  expect(sessionResponse.ok()).toBeTruthy();
  const session = (await sessionResponse.json()) as { id: string };
  const jobResponse = await request.post(
    `http://127.0.0.1:8000/sessions/${session.id}/jobs`,
    { data: { kind: "synthetic_base_flow" } },
  );
  expect(jobResponse.ok()).toBeTruthy();
  const job = (await jobResponse.json()) as { id: string };
  return job.id;
}

async function connectSlowClient(page: Page, jobId: string): Promise<void> {
  await page.evaluate(
    (id) =>
      new Promise<void>((resolve, reject) => {
        const state = globalThis as typeof globalThis & {
          previewDone?: Promise<PreviewMessage[]>;
        };
        const socket = new WebSocket(`ws://127.0.0.1:8000/ws/jobs/${id}/preview`);
        socket.addEventListener("open", () => {
          state.previewDone = new Promise<PreviewMessage[]>((done) => {
            const delivered: PreviewMessage[] = [];
            let pending: PreviewMessage | undefined;
            let terminal: PreviewMessage | undefined;
            let timer: ReturnType<typeof setTimeout> | undefined;
            const flush = () => {
              if (pending !== undefined) {
                delivered.push(pending);
                pending = undefined;
              }
              timer = undefined;
              if (terminal !== undefined) {
                delivered.push(terminal);
                done(delivered);
              }
            };
            socket.addEventListener("message", (event) => {
              const message = JSON.parse(String(event.data)) as PreviewMessage;
              if (message.type === "preview.update") {
                pending = message;
                timer ??= setTimeout(flush, 400);
              } else {
                terminal = message;
                if (timer === undefined) {
                  flush();
                }
              }
            });
          });
          resolve();
        });
        socket.addEventListener("error", () => reject(new Error("WebSocket no disponible.")));
      }),
    jobId,
  );
}

async function waitForPreviewMessages(page: Page): Promise<PreviewMessage[]> {
  return page.evaluate(async () => {
    const state = globalThis as typeof globalThis & {
      previewDone?: Promise<PreviewMessage[]>;
    };
    if (state.previewDone === undefined) {
      throw new Error("El cliente de preview no fue inicializado.");
    }
    return state.previewDone;
  });
}

test("supervisa un trabajo hasta recibir preview y estado terminal", async ({ page, request }) => {
  const jobId = await createJob(request);

  await page.goto(`/?job=${jobId}`);
  await expect(page.getByRole("status")).toHaveText("Previsualización conectada");
  const worker = startWorker(root);
  try {
    await expect(page.getByRole("img", { name: /Previsualización del frame/ })).toBeVisible();
    await expect(page.getByRole("status")).toHaveText("Trabajo finalizado");
    await expect(page.getByText("completed", { exact: true })).toBeVisible();
  } finally {
    stopWorker(worker);
  }
});

test("el cliente lento conserva la última preview antes del terminal", async ({ page, request }) => {
  const jobId = await createJob(request);
  await page.goto("/");
  await connectSlowClient(page, jobId);
  const worker = startWorker(root);
  try {
    const messages = await waitForPreviewMessages(page);
    const previews = messages.filter((message) => message.type === "preview.update");
    expect(previews).toHaveLength(1);
    expect(previews[0]?.frame_index).toBe(2);
    expect(messages.at(-1)).toMatchObject({ type: "job.terminal", status: "completed" });
  } finally {
    stopWorker(worker);
  }
});

test("desconectarse no bloquea el trabajo y una reconexión tardía obtiene el terminal", async ({
  page,
  request,
}) => {
  const jobId = await createJob(request);
  await page.goto("/");
  await page.evaluate(
    (id) =>
      new Promise<void>((resolve, reject) => {
        const socket = new WebSocket(`ws://127.0.0.1:8000/ws/jobs/${id}/preview`);
        socket.addEventListener("open", () => {
          socket.close();
          resolve();
        });
        socket.addEventListener("error", () => reject(new Error("WebSocket no disponible.")));
      }),
    jobId,
  );

  const worker = startWorker(root);
  try {
    await expect
      .poll(async () => {
        const response = await request.get(`http://127.0.0.1:8000/jobs/${jobId}`);
        return ((await response.json()) as { status: string }).status;
      })
      .toBe("completed");
  } finally {
    stopWorker(worker);
  }

  const message = await page.evaluate(
    (id) =>
      new Promise<PreviewMessage>((resolve, reject) => {
        const socket = new WebSocket(`ws://127.0.0.1:8000/ws/jobs/${id}/preview`);
        socket.addEventListener("message", (event) => {
          resolve(JSON.parse(String(event.data)) as PreviewMessage);
          socket.close();
        });
        socket.addEventListener("error", () => reject(new Error("WebSocket no disponible.")));
      }),
    jobId,
  );
  expect(message).toEqual(expect.objectContaining({ type: "job.terminal", status: "completed" }));
});

test("informa un trabajo inexistente", async ({ page }) => {
  await page.goto("/?job=00000000-0000-0000-0000-000000000000");
  await expect(page.getByRole("status")).toHaveText("Trabajo inexistente");
});
