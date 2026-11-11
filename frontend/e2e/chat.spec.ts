import path from "node:path";

import { expect, test } from "@playwright/test";

import { contrastRatio } from "./contrast";

// Recorridos principales contra el backend real con LLM guionizado (ver playwright.config.ts).
// Comparten un backend con estado y se ejecutan en orden: el tercero quita lo que crean los primeros.
const SAMPLE = path.resolve(__dirname, "../../backend/data/sample_docs/taskflow.md");

// Ni errores ni avisos en la consola: una violación de la CSP, un fallo de hidratación o un componente
// que pasa de no controlado a controlado aparecen ahí. Los 4xx esperados (p. ej. el 415) los registra
// el navegador como recurso fallido y se ignoran.
let consoleErrors: string[] = [];
test.beforeEach(({ page }) => {
  consoleErrors = [];
  page.on("pageerror", (error) => consoleErrors.push(error.message));
  page.on("console", (msg) => {
    const relevant = msg.type() === "error" || msg.type() === "warning";
    if (relevant && !msg.text().startsWith("Failed to load resource")) consoleErrors.push(`[${msg.type()}] ${msg.text()}`);
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
  await page.getByRole("alertdialog").getByRole("button", { name: "Quitar conversación" }).click();
  await expect(page.getByText(`Conversación «${title}» quitada.`)).toBeVisible();

  const docs = page.getByRole("list", { name: "Documentos indexados" });
  await docs.getByRole("button", { name: "Quitar taskflow.md" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Quitar documento" }).click();
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

test.describe("accesibilidad (auditoría de interfaz)", () => {
  test("la zona de subida muestra el foco del teclado y un nombre largo se lee entero", async ({ page }) => {
    await page.goto("/");
    const input = page.locator("aside input[type=file]").first();
    const shadow = () => input.evaluate((el) => getComputedStyle(el.closest("label")!).boxShadow);
    const before = await shadow();
    await input.focus();
    await page.keyboard.press("Shift+Tab");
    await page.keyboard.press("Tab"); // foco por teclado, no programático: activa :focus-visible
    await expect(input).toBeFocused();
    expect(await shadow()).not.toBe(before); // aparece el anillo en la zona (el input es invisible)

    const long = "guia-de-integracion-del-sistema-de-colas-distribuidas-version-2-con-ejemplos.md";
    await input.setInputFiles({ name: long, mimeType: "text/markdown", buffer: Buffer.from("# Colas\n\nTexto de prueba.") });
    const success = page.getByText(`${long} indexado`, { exact: false });
    await expect(success).toBeVisible();
    expect(await contrastRatio(success)).toBeGreaterThanOrEqual(4.5);
    const name = page.getByRole("list", { name: "Documentos indexados" }).getByText(long, { exact: true });
    await expect(name).toBeVisible();
    expect(await name.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(true);
    await page.getByRole("button", { name: `Quitar ${long}` }).click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Quitar documento" }).click();
  });

  test("un error de subida no desaparece solo", async ({ page }) => {
    await page.goto("/");
    await page.locator("aside input[type=file]").first().setInputFiles({
      name: "malo.exe", mimeType: "application/octet-stream", buffer: Buffer.from("MZ"),
    });
    const toast = page.getByText("Tipo de archivo no permitido: .exe");
    await expect(toast).toBeVisible();
    await page.waitForTimeout(5_000); // sonner cierra los avisos normales a los 4 s
    await expect(toast).toBeVisible();
    expect(await contrastRatio(toast)).toBeGreaterThanOrEqual(4.5);
    await page.getByRole("button", { name: "Cerrar aviso" }).click();
    await expect(toast).toBeHidden();
  });

  test.describe("con movimiento reducido", () => {
    test.use({ reducedMotion: "reduce", viewport: { width: 390, height: 800 } });

    test("el panel lateral aparece sin deslizarse", async ({ page }) => {
      await page.goto("/");
      await page.getByRole("button", { name: "Abrir conversaciones y documentos" }).click();
      const shift = await page
        .locator("[data-slot=sheet-content]")
        .evaluate((el) => getComputedStyle(el).getPropertyValue("--tw-enter-translate-x").trim());
      expect(shift).toBe("0");
    });
  });
});

// Texto pequeño: 4,5:1 (WCAG 1.4.3). Pares que fallaban antes de la auditoría de interfaz.
for (const scheme of ["light", "dark"] as const) {
  test(`contraste del texto en tema ${scheme === "light" ? "claro" : "oscuro"}`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: scheme });
    await page.goto("/");
    const box = page.getByLabel("Mensaje");
    await box.fill("¿Qué es TaskFlow?");
    await box.press("Enter");
    await expect(page).toHaveURL(/\/c\//, { timeout: 30_000 });

    // texto secundario de la conversación actual (sobre bg-muted)
    const current = page.locator("aside [aria-current=page] .text-muted-foreground").first();
    expect(await contrastRatio(current)).toBeGreaterThanOrEqual(4.5);

    // botón destructivo del diálogo de confirmación
    await page.getByRole("button", { name: /Quitar la conversación/ }).first().click();
    const confirm = page.getByRole("alertdialog").getByRole("button", { name: "Quitar conversación" });
    await expect(confirm).toBeVisible();
    expect(await contrastRatio(confirm)).toBeGreaterThanOrEqual(4.5);
    await page.keyboard.press("Escape");

    // mensaje de error del chat (rojo sobre su tinte)
    await page.route("**/api/chat/stream", (route) =>
      route.fulfill({ status: 502, contentType: "application/json", body: JSON.stringify({ detail: "El modelo no respondió correctamente. Inténtalo de nuevo." }) }),
    );
    await box.fill("otra pregunta");
    await box.press("Enter");
    const error = page.locator("main [role=alert]");
    await expect(error).toBeVisible();
    expect(await contrastRatio(error)).toBeGreaterThanOrEqual(4.5);
  });
}

test("cambiar de proveedor a mitad de una conversación y que la recuerde al recargar", async ({ page }) => {
  await page.goto("/");
  const box = page.getByLabel("Mensaje");
  const select = page.getByRole("combobox", { name: "Modelo" });
  await expect(select).toContainText("Claude");
  const claudeModel = ((await select.textContent()) ?? "").replace("Claude", "").trim();

  await box.fill("¿Qué es TaskFlow?");
  await box.press("Enter");
  const answers = page.getByTestId("agent-message");
  await expect(answers).toHaveCount(1);
  await expect(answers.nth(0).getByTestId("answered-by")).toHaveText(`Respondió Claude · ${claudeModel}`);

  await select.click();
  await page.getByRole("option", { name: /Gemini/ }).click();
  await expect(select).toContainText("Gemini");
  const geminiModel = ((await select.textContent()) ?? "").replace("Gemini", "").trim();
  await box.fill("¿Y cómo se reintenta?");
  await box.press("Enter");
  await expect(answers).toHaveCount(2);
  await expect(answers.nth(1)).toContainText("[gemini] Según la documentación");
  await expect(answers.nth(1).getByTestId("answered-by")).toHaveText(`Respondió Gemini · ${geminiModel}`);
  expect(await contrastRatio(answers.nth(1).getByTestId("answered-by"))).toBeGreaterThanOrEqual(4.5);
  const trace = page.getByRole("complementary", { name: "Pasos del agente" });
  await expect(trace.getByText("Claude", { exact: true })).toBeVisible();
  await expect(trace.getByText("Gemini", { exact: true })).toBeVisible();

  // la conversación recuerda el último proveedor
  await expect(page).toHaveURL(/\/c\//, { timeout: 30_000 });
  await page.reload();
  await expect(page.getByTestId("agent-message")).toHaveCount(2);
  await expect(page.getByRole("combobox", { name: "Modelo" })).toContainText("Gemini");

  // una conversación nueva vuelve al proveedor por defecto
  await page.getByRole("link", { name: "Nueva conversación" }).click();
  await expect(page.getByRole("combobox", { name: "Modelo" })).toContainText("Claude");
});

test.describe("selector de proveedor en pantalla estrecha", () => {
  test.use({ viewport: { width: 320, height: 700 } });

  test("con un proveedor no disponible seleccionado no desborda y el motivo se lee en la lista", async ({ page }) => {
    const reason = "Falta GEMINI_API_KEY en backend/.env, así que Gemini no se puede usar todavía.";
    await page.route("**/api/providers", (route) =>
      route.fulfill({
        json: [
          { id: "claude", label: "Claude", model: "claude-haiku-5-5", available: true, reason: null, default: false },
          { id: "gemini", label: "Gemini", model: "gemini-3.5-flash-lite", available: false, reason, default: true },
        ],
      }),
    );
    await page.goto("/");
    const select = page.getByRole("combobox", { name: "Modelo" });
    await expect(select).toContainText("Gemini");
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320);
    await select.click();
    await expect(page.getByRole("option", { name: /Gemini/ })).toContainText(reason);
  });
});
