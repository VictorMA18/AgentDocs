import path from "node:path";

import { expect, test } from "@playwright/test";

// Recorridos principales contra el backend real con LLM guionizado (ver playwright.config.ts).
// Comparten un backend con estado y se ejecutan en orden: el tercero quita lo que crean los primeros.
const SAMPLE = path.resolve(__dirname, "../../backend/data/sample_docs/taskflow.md");

// Ningún error en la consola: una violación de la CSP o un fallo de hidratación aparecen ahí.
// Los 4xx esperados (p. ej. el 415) los registra el navegador como recurso fallido y se ignoran.
let consoleErrors: string[] = [];
test.beforeEach(({ page }) => {
  consoleErrors = [];
  page.on("pageerror", (error) => consoleErrors.push(error.message));
  page.on("console", (msg) => {
    if (msg.type() === "error" && !msg.text().startsWith("Failed to load resource")) consoleErrors.push(msg.text());
  });
});
test.afterEach(() => expect(consoleErrors).toEqual([]));

test("subir un documento, preguntar y ver la respuesta con cita y los pasos", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("API conectada")).toBeVisible();

  // Subir: el input está dentro de la zona de subida (el visible es el de escritorio).
  await page.locator("aside input[type=file]").first().setInputFiles(SAMPLE);
  await expect(page.getByText(/taskflow\.md indexado: \d+ fragmentos/)).toBeVisible();
  await expect(page.getByRole("list", { name: "Documentos indexados" }).getByText("taskflow.md")).toBeVisible();

  // Preguntar con Enter: la URL pasa a /c/<id> y llega la respuesta en Markdown con la cita.
  const box = page.getByLabel("Mensaje");
  await box.fill("¿Qué es TaskFlow?");
  await box.press("Enter");
  await expect(page).toHaveURL(/\/c\/[0-9a-f]{32}$/);
  const answer = page.getByTestId("agent-message").last();
  await expect(answer).toContainText("Fuente: taskflow.md");
  await expect(answer.locator("pre code")).toContainText("print('hola')");
  await expect(answer.getByRole("button", { name: "Copiar" })).toBeVisible();

  // Pasos del agente y conversación guardada en la lista.
  const trace = page.getByRole("complementary", { name: "Pasos del agente" });
  await expect(trace.getByText("buscar_documentos")).toBeVisible();
  await expect(page.getByRole("list", { name: "Conversaciones guardadas" }).getByText("¿Qué es TaskFlow?")).toBeVisible();

  // Recargar reabre la misma conversación desde el servidor.
  await page.reload();
  await expect(page.getByTestId("agent-message").last()).toContainText("Fuente: taskflow.md");
});

test("pedir un diagrama, verlo dibujado y descargarlo", async ({ page }) => {
  await page.goto("/");
  const box = page.getByLabel("Mensaje");
  await box.fill("Hazme un diagrama de secuencia del login");
  await page.getByRole("button", { name: "Enviar" }).click();

  const artifact = page.getByTestId("artifact");
  await expect(artifact).toContainText("Flujo de login");
  await expect(artifact.locator(".mermaid-diagram svg")).toBeVisible(); // Mermaid lo dibujó

  const download = page.waitForEvent("download");
  await artifact.getByRole("link", { name: "Descargar" }).click();
  expect((await download).suggestedFilename()).toMatch(/^diagrama-flujo-de-login-.*\.mmd$/);
});

test("quitar una conversación y un documento con confirmación", async ({ page }) => {
  await page.goto("/");
  const conversations = page.getByRole("list", { name: "Conversaciones guardadas" });
  const first = conversations.getByRole("listitem").first();
  const title = (await first.getByRole("link").locator("span").first().textContent()) ?? "";
  await first.getByRole("button", { name: /Quitar la conversación/ }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Quitar" }).click();
  await expect(page.getByText(`Conversación «${title}» quitada.`)).toBeVisible();

  const docs = page.getByRole("list", { name: "Documentos indexados" });
  await docs.getByRole("button", { name: "Quitar taskflow.md" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Quitar" }).click();
  await expect(page.getByText("Aún no hay documentos indexados.")).toBeVisible();
});

test("un tipo de archivo no permitido muestra el error legible del backend", async ({ page }) => {
  await page.goto("/");
  await page.locator("aside input[type=file]").first().setInputFiles({
    name: "malo.exe", mimeType: "application/octet-stream", buffer: Buffer.from("MZ"),
  });
  await expect(page.getByText("Tipo de archivo no permitido: .exe")).toBeVisible();
});

test.describe("con el sistema en modo oscuro", () => {
  // El tema solo se conoce en el navegador: si algo del HTML inicial dependiera de él, React avisaría
  // de un desajuste al hidratar (lo recoge el afterEach). Con el tema claro por defecto no se vería.
  test.use({ colorScheme: "dark" });

  test("la página hidrata sin desajustes y el botón cambia el tema", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("html")).toHaveClass(/dark/);
    await page.getByRole("button", { name: "Cambiar entre modo claro y oscuro" }).click();
    await expect(page.locator("html")).not.toHaveClass(/dark/);
  });
});
