import path from "node:path";

import { expect, test, type Locator, type Page } from "@playwright/test";

import { PANEL_LIMITS } from "../src/lib/layout";

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

/** Panel de la conversación (Fase 12.C): fijo junto al chat en pantallas anchas o en un Sheet en las estrechas. */
function conversationPanel(page: Page) {
  return page
    .getByRole("complementary", { name: "Panel de la conversación" })
    .or(page.getByRole("dialog", { name: "Panel de la conversación" }));
}

/** Abre el panel (si no está a la vista) en una de sus pestañas. */
async function openPanelTab(page: Page, tab: "Documentos" | "Artefactos" | "Pasos") {
  const panel = conversationPanel(page);
  if (!(await panel.isVisible())) await page.getByRole("button", { name: "Panel de la conversación" }).click();
  await panel.getByRole("tab", { name: tab }).click();
  return panel;
}

/** El aviso (toast) que contiene un texto. */
const toast = (page: Page, text: string | RegExp) => page.locator("[data-sonner-toast]").filter({ hasText: text });

test("subir un documento, preguntar y ver la respuesta con cita y los pasos", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("API conectada")).toBeVisible();

  // Adjuntar con el clip del compositor en un chat nuevo: crea la conversación (la URL pasa a /c/<id>),
  // el aviso lo confirma y su acción abre la pestaña Documentos del panel; la barra resume los
  // documentos en una línea y el chat vacío propone preguntas sobre ellos (ADR-032, ADR-033).
  await page.locator("form [data-attach-input]").setInputFiles(SAMPLE);
  const added = toast(page, "Documento añadido");
  await expect(added).toContainText(/taskflow\.md · \d+ fragmentos/);
  await expect(page).toHaveURL(/\/c\/[0-9a-f]{32}$/);
  await expect(page.getByRole("button", { name: "Ver los documentos de esta conversación (1)" })).toContainText("MD");
  await added.getByRole("button", { name: "Ver documentos" }).click();
  const panel = conversationPanel(page);
  await expect(panel.getByRole("tab", { name: "Documentos" })).toHaveAttribute("aria-selected", "true");
  await expect(panel.getByRole("list", { name: "Documentos de esta conversación" }).getByText("taskflow.md")).toBeVisible();
  await expect(page.getByRole("list", { name: "Preguntas sugeridas" }).getByRole("button")).toHaveCount(4);

  // Preguntar con Enter: llega la respuesta en Markdown con la cita.
  const box = page.getByLabel("Mensaje");
  await box.fill("¿Qué es TaskFlow?");
  await box.press("Enter");
  const answer = page.getByTestId("agent-message").last();
  await expect(answer).toContainText("Fuente: taskflow.md");

  // La cita abre el texto del fragmento citado.
  const cite = answer.getByRole("button", { name: /Ver el fragmento \d+ de taskflow\.md/ });
  await cite.click();
  await expect(page.locator("[data-slot=popover-content]")).toContainText("taskflow.md");
  await expect(page.locator("[data-slot=popover-content] .prose-chat")).toContainText("TaskFlow");
  await page.keyboard.press("Escape");
  await expect(answer.locator("pre code")).toContainText("print('hola')");
  await expect(answer.getByRole("button", { name: "Copiar" })).toBeVisible();

  // Pasos del agente: la pestaña Pasos del panel; el botón de la cabecera lo cierra.
  await openPanelTab(page, "Pasos");
  await expect(panel.getByText("buscar_documentos").first()).toBeVisible();
  await page.getByRole("button", { name: "Panel de la conversación" }).click();
  await expect(panel).toBeHidden();
  await expect(page.getByRole("list", { name: "Conversaciones de hoy" }).getByText("¿Qué es TaskFlow?")).toBeVisible();

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

test("renombrar una conversación desde «Más opciones» y que el título se guarde", async ({ page }) => {
  await page.goto("/");
  const box = page.getByLabel("Mensaje");
  await box.fill("¿Qué es TaskFlow?");
  await box.press("Enter");
  await expect(page).toHaveURL(/\/c\//, { timeout: 30_000 });
  await expect(page.getByTestId("agent-message").last()).toContainText("Según la documentación");

  const row = page.getByRole("list", { name: "Conversaciones de hoy" }).getByRole("listitem").first();
  await row.getByRole("button", { name: /Más opciones de la conversación/ }).click();
  await page.getByRole("menuitem", { name: "Renombrar" }).click();
  // se escribe enseguida, sin esperar a que el menú termine de cerrarse: el campo ya tiene el foco
  await page.keyboard.press("ControlOrMeta+A");
  await page.keyboard.insertText("Qué es TaskFlow (renombrada)");
  await page.keyboard.press("Enter");
  await expect(toast(page, "Conversación renombrada")).toContainText("Ahora se llama «Qué es TaskFlow (renombrada)».");
  await expect(row.getByRole("button", { name: /Más opciones de la conversación Qué es TaskFlow \(renombrada\)/ })).toBeFocused();

  // la pestaña lleva el título completo de la conversación abierta (en el lateral puede cortarse)
  await expect(page).toHaveTitle("Qué es TaskFlow (renombrada) · TechDoc Agent");

  await page.reload();
  await expect(page.getByRole("link", { name: /Qué es TaskFlow \(renombrada\)/ })).toBeVisible();
});

test("buscar conversaciones por su contenido, también desde el riel", async ({ page }) => {
  await page.goto("/");
  const box = page.getByLabel("Mensaje");
  await box.fill("Hazme un diagrama de secuencia del login");
  await box.press("Enter");
  await expect(page.getByTestId("artifact")).toBeVisible({ timeout: 30_000 });

  // la respuesta guionizada dice «He generado el diagrama de secuencia del login»: se encuentra sin tildes
  const search = page.getByRole("searchbox", { name: "Buscar conversaciones" });
  await search.fill("GENERADO");
  await expect(page.getByRole("status").filter({ hasText: /encontrada/ })).toHaveText(/conversaci(ón|ones) encontradas?/);
  await expect(page.locator("#sidebar mark").first()).toHaveText(/generado/i);
  await search.press("Escape");
  await expect(search).toHaveValue("");

  // desde el riel: despliega el lateral y deja el foco en el buscador
  await page.getByRole("button", { name: "Ocultar conversaciones" }).click();
  await page.getByRole("button", { name: "Buscar conversaciones" }).click();
  await expect(search).toBeFocused();
});

test.describe("lateral en móvil", () => {
  test.use({ viewport: { width: 390, height: 800 } });

  test("al abrirlo el foco va al panel, no al buscador (no saca el teclado)", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Abrir conversaciones" }).click();
    const sheet = page.getByRole("dialog", { name: "TechDoc Agent" });
    await expect(sheet).toBeFocused();
    await expect(sheet.getByRole("searchbox", { name: "Buscar conversaciones" })).not.toBeFocused();
  });
});

test("quitar una conversación con confirmación", async ({ page }) => {
  await page.goto("/");
  const conversations = page.getByRole("list", { name: "Conversaciones de hoy" });
  const first = conversations.getByRole("listitem").first();
  const title = (await first.getByRole("link").locator("span").first().textContent()) ?? "";
  await first.getByRole("button", { name: /Más opciones de la conversación/ }).click();
  await page.getByRole("menuitem", { name: "Quitar" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Quitar conversación" }).click();
  await expect(toast(page, "Conversación quitada")).toContainText(`«${title}»`);

});

test("quitar un documento de una conversación con confirmación", async ({ page }) => {
  await page.goto("/");
  await page.locator("form [data-attach-input]").setInputFiles({ name: "quitar.md", mimeType: "text/markdown", buffer: Buffer.from("# Quitar\n\nTexto.") });
  // la barra resume y abre la pestaña Documentos, donde se quita
  await page.getByRole("button", { name: "Ver los documentos de esta conversación (1)" }).click();
  const list = conversationPanel(page).getByRole("list", { name: "Documentos de esta conversación" });
  await list.getByRole("button", { name: "Quitar quitar.md" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Quitar documento" }).click();
  await expect(toast(page, "Documento quitado")).toContainText("quitar.md ya no está en esta conversación.");
  await expect(conversationPanel(page).getByText("Esta conversación no tiene documentos")).toBeVisible();
  await expect(page.getByRole("button", { name: /Ver los documentos de esta conversación/ })).toHaveCount(0); // la barra no ocupa sitio
});

test("cada conversación ve solo sus documentos", async ({ page }) => {
  await page.goto("/");
  await page.locator("form [data-attach-input]").setInputFiles({ name: "solo-a.md", mimeType: "text/markdown", buffer: Buffer.from("# Solo A\n\nTexto de la conversación A.") });
  await expect(page.getByRole("button", { name: "Ver los documentos de esta conversación (1)" })).toBeVisible();
  await page.getByRole("link", { name: "Nueva conversación", exact: true }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("button", { name: /Ver los documentos de esta conversación/ })).toHaveCount(0);
  await expect(page.locator("main").getByText("solo-a.md")).toHaveCount(0); // en el lateral sí: es el título de la otra
});

test("soltar un archivo en el chat lo adjunta y una sugerencia se envía al pulsarla", async ({ page }) => {
  await page.goto("/");
  const chat = page.locator("main > div").first();
  const transfer = await page.evaluateHandle(() => {
    const data = new DataTransfer();
    data.items.add(new File(["# Soltado\n\nTaskFlow reintenta tres veces."], "soltado.md", { type: "text/markdown" }));
    return data;
  });
  await chat.dispatchEvent("dragenter", { dataTransfer: transfer });
  await expect(page.getByText("Suelta para añadir a esta conversación")).toBeVisible();
  await chat.dispatchEvent("drop", { dataTransfer: transfer });
  await expect(page.getByText("Suelta para añadir a esta conversación")).toBeHidden();
  await expect(toast(page, "Documento añadido")).toContainText("soltado.md");
  await expect(page).toHaveURL(/\/c\/[0-9a-f]{32}$/);

  await page.getByRole("button", { name: "Resume soltado.md" }).click();
  await expect(page.getByTestId("agent-message").last()).toContainText("Según la documentación");
  await expect(page.locator("main").getByText("Resume soltado.md", { exact: true })).toBeVisible();
});

test("un tipo de archivo no permitido muestra el error legible del backend y no crea conversación", async ({ page }) => {
  await page.goto("/");
  await page.locator("form [data-attach-input]").setInputFiles({
    name: "malo.exe", mimeType: "application/octet-stream", buffer: Buffer.from("MZ"),
  });
  await expect(page.getByText("Tipo de archivo no permitido: .exe")).toBeVisible();
  await expect(page).toHaveURL(/\/$/); // sin ningún documento, el chat nuevo sigue siendo nuevo
});

test.describe("con el sistema en modo oscuro", () => {
  // El tema solo se conoce en el navegador: si algo del HTML inicial dependiera de él, React avisaría
  // de un desajuste al hidratar (lo recoge el afterEach). Con el tema claro por defecto no se vería.
  test.use({ colorScheme: "dark" });

  test("la página hidrata sin desajustes y el menú de apariencia cambia el modo", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("html")).toHaveClass(/dark/);
    await page.getByRole("button", { name: "Apariencia" }).click();
    await page.getByRole("radio", { name: "Claro" }).click();
    await expect(page.locator("html")).not.toHaveClass(/dark/);
    // «Sistema» vuelve a seguir al sistema operativo (aquí, oscuro)
    await page.getByRole("radio", { name: "Sistema" }).click();
    await expect(page.locator("html")).toHaveClass(/dark/);
    await expect(page.getByRole("radio", { name: "Sistema" })).toBeChecked();
  });
});

test.describe("accesibilidad (auditoría de interfaz)", () => {
  test("el clip muestra el foco del teclado y un nombre largo se lee entero", async ({ page }) => {
    await page.goto("/");
    const clip = page.locator("form").getByRole("button", { name: "Adjuntar documentos" });
    await page.getByLabel("Mensaje").focus();
    await page.keyboard.press("Tab"); // del texto al clip (enviar está desactivado sin texto), por teclado
    await expect(clip).toBeFocused();
    expect(await clip.evaluate((el) => getComputedStyle(el).boxShadow)).not.toBe("none");

    const long = "guia-de-integracion-del-sistema-de-colas-distribuidas-version-2-con-ejemplos.md";
    await page.locator("form [data-attach-input]").setInputFiles({ name: long, mimeType: "text/markdown", buffer: Buffer.from("# Colas\n\nTexto de prueba.") });
    const success = toast(page, "Documento añadido");
    await expect(success).toContainText(long);
    // aviso del design system: título y detalle legibles sobre su superficie
    expect(await contrastRatio(success.locator(".app-toast-title"))).toBeGreaterThanOrEqual(4.5);
    expect(await contrastRatio(success.locator(".app-toast-description"))).toBeGreaterThanOrEqual(4.5);
    expect(await contrastRatio(success.locator(".app-toast-action"))).toBeGreaterThanOrEqual(4.5);
    const panel = await openPanelTab(page, "Documentos");
    const name = panel.getByRole("list", { name: "Documentos de esta conversación" }).getByText(long, { exact: true });
    await expect(name).toBeVisible();
    expect(await name.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(true); // se parte, no se corta
    expect(await contrastRatio(page.locator(".file-badge").first())).toBeGreaterThanOrEqual(4.5);
  });

  test("un error de subida no desaparece solo", async ({ page }) => {
    await page.goto("/");
    await page.locator("form [data-attach-input]").setInputFiles({
      name: "malo.exe", mimeType: "application/octet-stream", buffer: Buffer.from("MZ"),
    });
    const error = toast(page, "No se pudo añadir malo.exe");
    await expect(error).toContainText("Tipo de archivo no permitido: .exe");
    await page.waitForTimeout(6_000); // los avisos de éxito se cierran a los 5 s; los errores no
    await expect(error).toBeVisible();
    expect(await contrastRatio(error.locator(".app-toast-title"))).toBeGreaterThanOrEqual(4.5);
    expect(await contrastRatio(error.locator(".app-toast-description"))).toBeGreaterThanOrEqual(4.5);
    await error.getByRole("button", { name: "Cerrar aviso" }).click();
    await expect(error).toBeHidden();
  });

  test.describe("en una ventana baja", () => {
    test.use({ viewport: { width: 1280, height: 440 } });

    test("un control enfocado con el teclado no queda tapado por el compositor (WCAG 2.4.11)", async ({ page }) => {
      await page.goto("/");
      const box = page.getByLabel("Mensaje");
      for (const question of ["¿Qué es TaskFlow?", "¿Y cómo se crea una tarea?"]) {
        await box.fill(question);
        await box.press("Enter");
        await expect(page.getByTestId("answered-by")).toHaveCount(question.startsWith("¿Qué") ? 1 : 2, { timeout: 30_000 });
      }
      // se deja el último «Copiar» detrás del compositor y se llega a él con Tab desde el control anterior
      const hidden = await page.evaluate(() => {
        const scroller = document.querySelector<HTMLElement>("[data-chat-scroll]")!;
        const panel = document.querySelector("form [data-surface=panel]")!.getBoundingClientRect();
        const copies = [...document.querySelectorAll<HTMLElement>("[role=log] button")].filter((b) => b.textContent?.includes("Copiar"));
        const target = copies.at(-1)!;
        const before = copies.at(-2) ?? document.querySelector<HTMLElement>("aside button")!;
        const rect = target.getBoundingClientRect();
        scroller.scrollTop += rect.top - (panel.top + panel.height / 2 - rect.height / 2);
        before.focus({ preventScroll: true });
        const now = target.getBoundingClientRect();
        const panelNow = document.querySelector("form [data-surface=panel]")!.getBoundingClientRect();
        return now.top >= panelNow.top && now.bottom <= panelNow.bottom;
      });
      expect(hidden).toBe(true); // precondición: está detrás
      await page.keyboard.press("Tab");
      const after = await page.evaluate(() => {
        const el = document.activeElement!.getBoundingClientRect();
        const panel = document.querySelector("form [data-surface=panel]")!.getBoundingClientRect();
        return { label: document.activeElement!.textContent, bottom: el.bottom, panelTop: panel.top };
      });
      expect(after.label).toContain("Copiar");
      expect(after.bottom).toBeLessThanOrEqual(after.panelTop);
    });
  });

  test.describe("con movimiento reducido", () => {
    test.use({ reducedMotion: "reduce", viewport: { width: 390, height: 800 } });

    test("el panel lateral aparece sin deslizarse", async ({ page }) => {
      await page.goto("/");
      await page.getByRole("button", { name: "Abrir conversaciones" }).click();
      const shift = await page
        .locator("[data-slot=sheet-content]")
        .evaluate((el) => getComputedStyle(el).getPropertyValue("--tw-enter-translate-x").trim());
      expect(shift).toBe("0");
    });
  });
});

// Apariencia de partida de una prueba: next-themes guarda la luminosidad en "theme" y la app el
// estilo, el tinte y la fuente en "techdoc-appearance" (ADR-029). Se escribe antes de cada carga.
type Tint = "neutral" | "red" | "blue" | "green" | "orange";
type Look = { theme: "light" | "dark"; style: "classic" | "glass"; font?: "geist" | "dm-sans"; tint?: Tint };
function startWith(page: Page, { theme, style, font = "geist", tint = "neutral" }: Look) {
  return page.addInitScript(
    ([t, a]) => {
      localStorage.setItem("theme", t);
      localStorage.setItem("techdoc-appearance", a);
    },
    [theme, JSON.stringify({ style, tint, font })] as const,
  );
}

// Los 20 temas: 2 estilos × 5 colores × claro/oscuro (ADR-030).
const TINT_NAMES: Record<Tint, string> = { neutral: "neutro", red: "rojo", blue: "azul", green: "verde", orange: "naranja" };
const THEMES: { name: string; look: Look }[] = (["classic", "glass"] as const).flatMap((style) =>
  (Object.keys(TINT_NAMES) as Tint[]).flatMap((tint) =>
    (["light", "dark"] as const).map((theme) => ({
      name: `${style === "classic" ? (theme === "light" ? "Claro" : "Oscuro") : `Glass con base ${theme === "light" ? "blanca" : "negra"}`} ${TINT_NAMES[tint]}`,
      look: { theme, style, tint },
    })),
  ),
);

// Texto pequeño: 4,5:1 (WCAG 1.4.3) en los 20 temas. En Glass el fondo es translúcido: contrastRatio
// mide sobre el color base y sobre las manchas del fondo y se queda con el peor.
for (const { name, look } of THEMES) {
  test(`tema ${name}: contraste del texto, foco del compositor y consola limpia`, async ({ page }) => {
    await startWith(page, look);
    await page.goto("/");
    await expect(page.locator("html")).toHaveAttribute("data-style", look.style);
    if (look.style === "glass") {
      // el cristal está aplicado: el compositor desenfoca lo que pasa por detrás, y ningún antecesor suyo
      // tiene backdrop-filter ni mask (en Chrome lo convertirían en «backdrop root» y el cristal dejaría
      // de desenfocar los mensajes que se desplazan)
      const glass = await page.locator("form [data-surface=panel]").evaluate((el) => {
        const roots: string[] = [];
        for (let node = el.parentElement; node; node = node.parentElement) {
          const css = getComputedStyle(node);
          if (css.backdropFilter !== "none" || css.maskImage !== "none") roots.push(node.tagName);
        }
        return { filter: getComputedStyle(el).backdropFilter, roots };
      });
      expect(glass.filter).toContain("blur");
      expect(glass.roots).toEqual([]);
    }
    const atLeast = async (locator: Locator) => expect(await contrastRatio(locator)).toBeGreaterThanOrEqual(4.5);

    await atLeast(page.getByRole("heading", { name: "TechDoc Agent" }));
    // pulgar de las barras de desplazamiento: 3:1 contra el panel (WCAG 1.4.11; tiene color propio)
    await page.evaluate(() => {
      const probe = document.createElement("span");
      probe.id = "scrollbar-probe";
      probe.textContent = "▮";
      probe.style.color = "var(--scrollbar-thumb)";
      document.querySelector("aside")!.append(probe);
    });
    expect(await contrastRatio(page.locator("#scrollbar-probe"))).toBeGreaterThanOrEqual(3);
    await page.evaluate(() => document.getElementById("scrollbar-probe")!.remove());
    await atLeast(page.getByTestId("char-count"));
    await atLeast(page.locator("#provider-label"));

    // tooltip (texto con el color base sobre el del texto: el base tiene que ser opaco)
    await page.getByRole("button", { name: "Apariencia" }).hover();
    await atLeast(page.getByRole("tooltip"));

    // texto de éxito al adjuntar un documento (verde sobre su tinte), su chip con el tipo y una sugerencia
    const file = `tema-${look.style}-${look.tint}-${look.theme}.md`;
    await page.locator("form [data-attach-input]").setInputFiles({ name: file, mimeType: "text/markdown", buffer: Buffer.from("# Tema\n\n¿Qué es TaskFlow? TaskFlow organiza el trabajo en tareas.") });
    // aviso del design system: título, detalle y acción sobre su superficie (en Glass, cristal)
    const indexed = toast(page, "Documento añadido");
    await expect(indexed).toContainText(file);
    await atLeast(indexed.locator(".app-toast-title"));
    await atLeast(indexed.locator(".app-toast-description"));
    await atLeast(indexed.locator(".app-toast-action"));
    // la ✕ del aviso: icono legible (3:1, WCAG 1.4.11) y sin el fondo propio de sonner en oscuro
    expect(await contrastRatio(indexed.getByRole("button", { name: "Cerrar aviso" }))).toBeGreaterThanOrEqual(3);
    expect(await indexed.getByRole("button", { name: "Cerrar aviso" }).evaluate((el) => getComputedStyle(el).backgroundColor)).toBe(
      "rgba(0, 0, 0, 0)",
    );
    // tras la primera subida la vista pasa a /c/<id> y se vuelve a montar: se mide cuando se estabiliza
    await expect(page).toHaveURL(/\/c\/[0-9a-f]{32}$/);
    const summary = page.getByRole("button", { name: "Ver los documentos de esta conversación (1)" });
    await expect.poll(() => contrastRatio(summary)).toBeGreaterThanOrEqual(4.5);
    await expect.poll(() => contrastRatio(summary.locator(".file-badge"))).toBeGreaterThanOrEqual(4.5);
    // las sugerencias entran con GSAP (fundido): se mide cuando ya son opacas
    const suggestions = page.getByRole("list", { name: "Preguntas sugeridas" });
    await expect(suggestions).toHaveCSS("opacity", "1");
    await atLeast(suggestions.getByRole("button").first());

    // foco del teclado en la caja de texto: se marca el contorno de todo el compositor
    const box = page.getByLabel("Mensaje");
    const panel = page.locator("form [data-surface=panel]");
    await box.focus();
    await page.keyboard.press("Shift+Tab");
    await page.keyboard.press("Tab");
    await expect(box).toBeFocused();
    expect(await panel.evaluate((el) => getComputedStyle(el).outlineStyle)).toBe("solid");

    await box.fill("¿Qué es TaskFlow?");
    await box.press("Enter");
    await expect(page).toHaveURL(/\/c\//, { timeout: 30_000 });
    const answer = page.getByTestId("agent-message").last();
    await expect(answer).toContainText("Según la documentación");
    await atLeast(answer.locator("p").first());
    await atLeast(answer.getByTestId("answered-by"));
    // la cita (chip con su tipo) y su número de fragmento en gris; con el teclado se ve el foco
    const cite = answer.getByRole("button", { name: /Ver el fragmento/ });
    await atLeast(cite.locator("span.break-all"));
    await atLeast(cite.locator(".text-muted-foreground"));
    await atLeast(cite.locator(".file-badge"));
    // «Añadir» de la barra y el panel de la conversación: documento, fragmentos y pestañas (también la no
    // elegida, en gris); el foco del teclado en las pestañas se ve
    await atLeast(page.getByRole("button", { name: "Añadir documentos" }).first());
    const convPanel = await openPanelTab(page, "Documentos");
    const item = convPanel.getByRole("list", { name: "Documentos de esta conversación" }).getByRole("listitem").first();
    await atLeast(item.getByText(file, { exact: true }));
    await atLeast(item.locator(".text-muted-foreground"));
    await atLeast(item.locator(".file-badge"));
    await atLeast(convPanel.getByRole("tab", { name: "Artefactos" }));
    await atLeast(convPanel.getByRole("tab", { name: "Documentos" }));
    await convPanel.getByRole("tab", { name: "Documentos" }).focus();
    await page.keyboard.press("ArrowRight"); // por teclado: se ve el foco y cambia de pestaña (APG)
    const artifactsTab = convPanel.getByRole("tab", { name: "Artefactos" });
    await expect(artifactsTab).toBeFocused();
    expect(await artifactsTab.evaluate((el) => getComputedStyle(el).boxShadow)).not.toBe("none");
    await atLeast(convPanel.getByText("Aún no hay artefactos en esta conversación"));
    await page.getByRole("button", { name: "Panel de la conversación" }).click(); // se cierra para seguir
    // la burbuja del usuario lleva el acento del color elegido (texto sobre --primary)
    await atLeast(page.locator("main").getByText("¿Qué es TaskFlow?", { exact: true }));
    // el compositor va pegado abajo y los mensajes pasan por detrás, pero al final el último queda encima
    await expect(answer.getByTestId("logo-claude")).toBeVisible();
    const [answerBox, panelBox] = await Promise.all([answer.boundingBox(), panel.boundingBox()]);
    expect(answerBox!.y + answerBox!.height).toBeLessThanOrEqual(panelBox!.y);

    // texto secundario de la conversación actual (sobre bg-muted)
    await atLeast(page.locator("aside [aria-current=page] .text-muted-foreground").first());

    // botón destructivo del diálogo de confirmación (capa flotante), abierto desde «Más opciones»
    await page.getByRole("button", { name: /Más opciones de la conversación/ }).first().click();
    await atLeast(page.getByRole("menuitem", { name: "Quitar" }));
    await page.getByRole("menuitem", { name: "Quitar" }).click();
    const confirm = page.getByRole("alertdialog").getByRole("button", { name: "Quitar conversación" });
    await expect(confirm).toBeVisible();
    await atLeast(confirm);
    await atLeast(page.locator("[data-slot=alert-dialog-description]"));
    await page.keyboard.press("Escape");

    // riel del lateral plegado: icono legible (3:1, WCAG 1.4.11) y foco visible
    await page.getByRole("button", { name: "Ocultar conversaciones" }).focus();
    await page.keyboard.press("Enter"); // con el teclado: el foco que pasa al riel se ve (:focus-visible)
    const expand = page.getByRole("button", { name: "Mostrar conversaciones" });
    await expect(expand).toBeFocused();
    expect(await contrastRatio(expand)).toBeGreaterThanOrEqual(3);
    expect(await expand.evaluate((el) => getComputedStyle(el).boxShadow)).not.toBe("none");
    await expand.click();

    // mensaje de error del chat (rojo sobre su tinte)
    await page.route("**/api/chat/stream", (route) =>
      route.fulfill({ status: 502, contentType: "application/json", body: JSON.stringify({ detail: "El modelo no respondió correctamente. Inténtalo de nuevo." }) }),
    );
    await box.fill("otra pregunta");
    await box.press("Enter");
    const error = page.locator("main [role=alert]");
    await expect(error).toBeVisible();
    await atLeast(error);
  });
}

test.describe("menú de apariencia", () => {
  test("la elección se guarda, se aplica antes de hidratar y la fuente cambia de verdad", async ({ page }) => {
    // valor de data-style al terminar de leer el HTML: lo pone el script, no React al hidratar
    await page.addInitScript(() =>
      document.addEventListener("DOMContentLoaded", () => {
        (window as unknown as { styleAtLoad?: string }).styleAtLoad = document.documentElement.dataset.style;
      }),
    );
    await page.goto("/");
    await page.getByRole("button", { name: "Apariencia" }).click();
    const menu = page.getByRole("dialog", { name: "Apariencia" });
    const fontRadio = page.getByRole("radio", { name: "DM Sans" });
    // se mide con la animación de entrada del panel ya terminada
    await menu.evaluate((el) => Promise.all(el.getAnimations().map((a) => a.finished)));
    const before = { menu: await menu.boundingBox(), font: await fontRadio.boundingBox() };
    await page.getByRole("radio", { name: "Glass" }).click();
    await expect(page.locator("html")).toHaveAttribute("data-style", "glass");
    // los grupos son siempre los mismos: el panel no cambia de tamaño y nada se mueve bajo el cursor
    expect(await menu.boundingBox()).toEqual(before.menu);
    expect(await fontRadio.boundingBox()).toEqual(before.font);
    await page.getByRole("radio", { name: "Oscuro" }).click();
    await fontRadio.click();
    await expect(page.locator("html")).toHaveAttribute("data-style", "glass");

    await page.reload();
    const html = page.locator("html");
    await expect(html).toHaveAttribute("data-style", "glass");
    await expect(html).toHaveAttribute("data-font", "dm-sans");
    await expect(html).toHaveClass(/dark/);
    expect(await page.evaluate(() => (window as unknown as { styleAtLoad?: string }).styleAtLoad)).toBe("glass");
    expect(await page.locator("body").evaluate((el) => getComputedStyle(el).fontFamily)).toContain("DM Sans");

    // volver a Clásico conserva el tema y la fuente elegidos
    await page.getByRole("button", { name: "Apariencia" }).click();
    await page.getByRole("radio", { name: "Clásico" }).click();
    await expect(html).toHaveAttribute("data-style", "classic");
    await expect(html).toHaveClass(/dark/);
    await expect(html).toHaveAttribute("data-font", "dm-sans");
    await page.getByRole("radio", { name: "Claro" }).click();
    await expect(html).not.toHaveClass(/dark/);
  });

  test("la mancha del fondo de Glass se mueve y se puede parar", async ({ page }) => {
    await startWith(page, { theme: "light", style: "glass" });
    await page.goto("/");
    const blob = () => page.evaluate(() => getComputedStyle(document.body, "::before").animationName);
    expect(await blob()).toBe("blob-drift");
    await page.getByRole("button", { name: "Apariencia" }).click();
    await page.getByRole("radio", { name: "Quieto" }).click();
    await expect(page.locator("html")).toHaveAttribute("data-motion", "off");
    expect(await blob()).toBe("none");
    // en Clásico el grupo no aplica: se desactiva y dice por qué
    await page.getByRole("radio", { name: "Clásico" }).click();
    await expect(page.getByRole("radio", { name: "En movimiento" })).toBeDisabled();
    await expect(page.getByRole("radiogroup", { name: /Fondo · solo con Glass/ })).toBeVisible();
  });

  test.describe("con movimiento reducido", () => {
    test.use({ reducedMotion: "reduce" });

    test("la mancha del fondo no se mueve y el menú explica por qué", async ({ page }) => {
      await startWith(page, { theme: "dark", style: "glass" });
      await page.goto("/");
      expect(await page.evaluate(() => getComputedStyle(document.body, "::before").animationName)).toBe("none");
      await page.getByRole("button", { name: "Apariencia" }).click();
      await expect(page.getByRole("radiogroup", { name: /tu sistema pide menos movimiento/ })).toBeVisible();
    });
  });

    test("el color se elige con muestras, se nota en el acento y se guarda", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Apariencia" }).click();
    const blue = page.getByRole("radio", { name: "Azul" });
    const swatch = blue.locator("[data-swatch]");
    const radius = () => swatch.evaluate((el) => parseFloat(getComputedStyle(el).borderTopLeftRadius));
    expect(await radius()).toBe(6); // cuadrado redondeado (6 px)
    await blue.click();
    await expect(page.locator("html")).toHaveAttribute("data-tint", "blue");
    await expect(blue).toBeChecked();
    await expect.poll(radius).toBeGreaterThan(12); // la elegida pasa a círculo (y lleva anillo y ✓)
    // el acento cambia: la opción marcada de los grupos usa --primary, que ahora es azul
    const checked = await page.getByRole("radio", { name: "Clásico" }).evaluate((el) => getComputedStyle(el).backgroundColor);
    const [r, , b] = checked.match(/[\d.]+/g)!.map(Number);
    expect(b).toBeGreaterThan(r);
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-tint", "blue");
  });

// DM Sans es más ancha que Geist: a 320 px nada debe desbordar con ninguna de las dos.
  for (const font of ["geist", "dm-sans"] as const) {
    test.describe(`a 320 px con ${font === "geist" ? "Geist" : "DM Sans"}`, () => {
      test.use({ viewport: { width: 320, height: 700 } });

      test("Glass no desborda, ni con el menú abierto", async ({ page }) => {
        await startWith(page, { theme: "light", style: "glass", font });
        await page.goto("/");
        await expect(page.getByRole("combobox", { name: "Modelo" })).toContainText("Claude");
        const width = () => page.evaluate(() => document.documentElement.scrollWidth);
        expect(await width()).toBeLessThanOrEqual(320);
        await page.getByRole("button", { name: "Apariencia" }).click();
        const menu = page.getByRole("dialog", { name: "Apariencia" });
        await expect(menu).toBeVisible();
        const box = await menu.boundingBox();
        expect(box!.x).toBeGreaterThanOrEqual(0);
        expect(box!.x + box!.width).toBeLessThanOrEqual(320);
        expect(await width()).toBeLessThanOrEqual(320);
      });
    });
  }
});

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

  // El primer mensaje pasa a /c/<id>; en desarrollo esa ruta se compila la primera vez y la vista se
  // vuelve a montar segundos después. Se espera a que termine antes de abrir el selector (con él abierto,
  // el montaje nuevo dejaba la opción tapada y la prueba fallaba de vez en cuando).
  await expect(page).toHaveURL(/\/c\/[0-9a-f]{32}$/);
  await expect(answers.nth(0).getByTestId("answered-by")).toBeVisible();

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
  const trace = await openPanelTab(page, "Pasos");
  await expect(trace.getByText("Claude", { exact: true })).toBeVisible();
  await expect(trace.getByText("Gemini", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Panel de la conversación" }).click();
  await expect(trace).toBeHidden();

  // la conversación recuerda el último proveedor
  await expect(page).toHaveURL(/\/c\//, { timeout: 30_000 });
  await page.reload();
  await expect(page.getByTestId("agent-message")).toHaveCount(2);
  await expect(page.getByRole("combobox", { name: "Modelo" })).toContainText("Gemini");

  // una conversación nueva vuelve al proveedor por defecto
  await page.getByRole("link", { name: "Nueva conversación", exact: true }).click();
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

test.describe("paneles ajustables", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test("el lateral se ensancha arrastrando, con el teclado y con un clic, y recuerda el ancho", async ({ page }) => {
    await page.goto("/");
    const sidebar = page.locator("#sidebar");
    const handle = page.getByRole("separator", { name: "Ancho del panel de conversaciones" });
    const width = async () => Math.round((await sidebar.boundingBox())!.width);
    expect(await width()).toBe(288);

    // arrastrar 40 px a la derecha
    const box = (await handle.boundingBox())!;
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width / 2 + 40, box.y + box.height / 2, { steps: 5 });
    await page.mouse.up();
    expect(await width()).toBe(328);
    await expect(handle).toHaveAttribute("aria-valuenow", "328");

    // teclado
    await handle.focus();
    await page.keyboard.press("ArrowLeft");
    expect(await width()).toBe(312);
    await page.keyboard.press("Home");
    expect(await width()).toBe(PANEL_LIMITS.sidebar.min); // el autor ajusta este mínimo en lib/layout.ts

    // un clic sin arrastrar pasa al tamaño siguiente (alternativa sin arrastre, WCAG 2.5.7)
    await handle.click();
    expect(await width()).toBe(288);

    // se recuerda al recargar, sin aviso de hidratación (lo vigila el afterEach)
    await page.keyboard.press("End");
    await page.reload();
    // el máximo deja sitio al chat (PANEL_LIMITS en lib/layout.ts)
    expect(await width()).toBe(PANEL_LIMITS.sidebar.max);
    await expect(handle).toHaveAttribute("aria-valuenow", String(PANEL_LIMITS.sidebar.max));
  });

  test("el lateral se pliega a un riel arrastrando, con Intro y con su botón, y lo recuerda", async ({ page }) => {
    await page.goto("/");
    const sidebar = page.locator("#sidebar");
    const handle = page.getByRole("separator", { name: "Ancho del panel de conversaciones" });
    const width = async () => Math.round((await sidebar.boundingBox())!.width);
    const settled = () => sidebar.evaluate((el) => Promise.allSettled(el.getAnimations().map((a) => a.finished)));
    const expand = page.getByRole("button", { name: "Mostrar conversaciones" });

    // arrastrar por debajo del umbral avisa (se atenúa) y pliega al soltar
    const box = (await handle.boundingBox())!;
    const y = box.y + box.height / 2;
    await page.mouse.move(box.x + box.width / 2, y);
    await page.mouse.down();
    await page.mouse.move(box.x - 200, y, { steps: 6 });
    await expect(handle).toHaveAttribute("data-collapse", "armed");
    await expect.poll(() => sidebar.evaluate((el) => getComputedStyle(el).opacity)).toBe("0.5");
    await page.mouse.up();
    await settled();
    expect(await width()).toBe(56);
    await expect(handle).toHaveAttribute("aria-valuetext", "Plegado");
    await expect(expand).toBeVisible();
    await expect(page.getByRole("list", { name: /Conversaciones de/ })).toHaveCount(0); // el contenido no está a la vista
    // los iconos del riel van centrados en él
    const rail = (await sidebar.boundingBox())!;
    for (const button of await page.getByRole("navigation", { name: "Lateral plegado" }).getByRole("button").all()) {
      const b = (await button.boundingBox())!;
      expect(Math.abs(b.x + b.width / 2 - (rail.x + rail.width / 2))).toBeLessThanOrEqual(1);
    }

    // se recuerda al recargar, sin aviso de hidratación ni salto (lo vigila el afterEach)
    await page.reload();
    expect(await width()).toBe(56);

    // el riel lo despliega y el foco pasa al botón que lo vuelve a plegar
    await expand.focus();
    await page.keyboard.press("Enter");
    await settled();
    expect(await width()).toBe(288);
    await expect(page.getByRole("button", { name: "Ocultar conversaciones" })).toBeFocused();

    // Intro en el separador lo pliega y lo restaura (patrón Window Splitter de ARIA APG)
    await handle.focus();
    await page.keyboard.press("Enter");
    await settled();
    expect(await width()).toBe(56);
    await page.keyboard.press("Enter");
    await settled();
    expect(await width()).toBe(288);
  });

  test("con movimiento reducido el lateral se pliega sin animar el ancho", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/");
    const sidebar = page.locator("#sidebar");
    await page.getByRole("button", { name: "Ocultar conversaciones" }).click();
    expect(await sidebar.evaluate((el) => [getComputedStyle(el).transitionDuration, el.getAnimations().length])).toEqual(["0s", 0]);
    expect(Math.round((await sidebar.boundingBox())!.width)).toBe(56);
  });

  test("el panel de la conversación va fijo junto al chat, se ensancha desde su borde y se recuerda abierto", async ({ page }) => {
    await page.goto("/");
    const panel = await openPanelTab(page, "Pasos");
    await expect(page.getByRole("complementary", { name: "Panel de la conversación" })).toBeVisible(); // fijo, no encima
    await expect(page.getByRole("button", { name: "Panel de la conversación" })).toHaveAttribute("aria-expanded", "true");
    const width = async () => Math.round((await panel.boundingBox())!.width);
    expect(await width()).toBe(384);
    const handle = page.getByRole("separator", { name: "Ancho del panel de la conversación" });
    await handle.focus();
    await page.keyboard.press("ArrowLeft");
    expect(await width()).toBe(400);
    // se recuerda abierto (y su ancho) al recargar, sin aviso de hidratación (lo vigila el afterEach)
    await page.reload();
    await expect(conversationPanel(page)).toBeVisible();
    expect(await width()).toBe(400);
  });

  test.describe("en una pantalla estrecha", () => {
    test.use({ viewport: { width: 1024, height: 800 } });

    test("el panel se abre encima del chat y Esc lo cierra", async ({ page }) => {
      await page.goto("/");
      await page.getByRole("button", { name: "Panel de la conversación" }).click();
      const sheet = page.getByRole("dialog", { name: "Panel de la conversación" });
      await expect(sheet.getByRole("tab", { name: "Documentos" })).toBeVisible();
      await page.keyboard.press("Escape");
      await expect(sheet).toBeHidden();
    });
  });
});

test.describe("animaciones de los momentos clave (GSAP)", () => {
  // Registra los estilos en línea de los mensajes nuevos: así se ve si entraron desplazándose.
  async function recordEntrances(page: Page) {
    await page.addInitScript(() => {
      const seen: string[] = [];
      (window as unknown as { entrances: string[] }).entrances = seen;
      new MutationObserver((records) => {
        for (const record of records) {
          const el = record.target as HTMLElement;
          if (el.dataset?.messageId && el.getAttribute("style")) seen.push(el.getAttribute("style")!);
        }
      }).observe(document, { subtree: true, attributes: true, attributeFilter: ["style"] });
    });
  }
  const sendAndCollect = async (page: Page) => {
    await page.goto("/");
    const box = page.getByLabel("Mensaje");
    await box.fill("¿Qué es TaskFlow?");
    await box.press("Enter");
    await expect(page.getByTestId("agent-message")).toBeVisible();
    await page.waitForTimeout(500);
    return page.evaluate(() => (window as unknown as { entrances: string[] }).entrances.join(" | "));
  };

  test("un mensaje nuevo entra con fundido y un pequeño desplazamiento", async ({ page }) => {
    await recordEntrances(page);
    expect(await sendAndCollect(page)).toMatch(/translate/);
  });

  test.describe("con movimiento reducido", () => {
    test.use({ reducedMotion: "reduce" });

    test("los mensajes nuevos solo aparecen con un fundido: nada se desplaza ni se desenfoca", async ({ page }) => {
      await recordEntrances(page);
      const styles = await sendAndCollect(page);
      expect(styles).toMatch(/opacity/);
      expect(styles).not.toMatch(/translate|blur/);
    });
  });
});

test.describe("documentos en el chat (Fase 12.B)", () => {
  test("la cita y los botones de los chips muestran el foco del teclado", async ({ page }) => {
    await page.goto("/");
    await page.locator("form [data-attach-input]").setInputFiles({ name: "foco.md", mimeType: "text/markdown", buffer: Buffer.from("# Foco\n\nTaskFlow reintenta tres veces.") });
    await expect(page.getByRole("button", { name: "Ver los documentos de esta conversación (1)" })).toBeVisible();
    const box = page.getByLabel("Mensaje");
    await box.fill("¿Cuántas veces reintenta TaskFlow?");
    await box.press("Enter");
    const cite = page.getByTestId("agent-message").last().getByRole("button", { name: /Ver el fragmento/ });
    await expect(cite).toBeVisible();
    await openPanelTab(page, "Documentos");
    for (const control of [cite, page.getByRole("button", { name: "Quitar foco.md" })]) {
      await control.focus();
      await page.keyboard.press("Shift+Tab");
      await page.keyboard.press("Tab"); // por teclado: activa :focus-visible
      await expect(control).toBeFocused();
      expect(await control.evaluate((el) => getComputedStyle(el).boxShadow)).not.toBe("none");
    }
    // Intro abre la cita y Esc la cierra devolviendo el foco
    await cite.focus();
    await page.keyboard.press("Enter");
    await expect(page.locator("[data-slot=popover-content]")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(cite).toBeFocused();
  });

  test.describe("en móvil", () => {
    test.use({ viewport: { width: 320, height: 700 } });

    test("la barra resume los documentos en una línea, abre el panel encima y nada desborda", async ({ page }) => {
      await page.goto("/");
      await page.locator("form [data-attach-input]").setInputFiles([
        { name: "uno.md", mimeType: "text/markdown", buffer: Buffer.from("# Uno\n\nTexto.") },
        { name: "dos.md", mimeType: "text/markdown", buffer: Buffer.from("# Dos\n\nTexto.") },
      ]);
      await expect(toast(page, "2 documentos añadidos")).toBeVisible();
      const summary = page.getByRole("button", { name: "Ver los documentos de esta conversación (2)" });
      await expect(summary).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320);
      await summary.click();
      const sheet = page.getByRole("dialog", { name: "Panel de la conversación" });
      await expect(sheet.getByRole("list", { name: "Documentos de esta conversación" }).getByText("uno.md")).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320);
    });
  });
});

test.describe("artefactos y «Nueva conversación» (Fase 12.C)", () => {
  test("un diagrama aparece en Artefactos, se abre desde su tarjeta, se descarga desde el panel y lleva de vuelta al chat", async ({ page }) => {
    await page.goto("/");
    const box = page.getByLabel("Mensaje");
    await box.fill("Hazme un diagrama de secuencia del login");
    await box.press("Enter");
    const card = page.getByTestId("artifact");
    await expect(card.locator(".mermaid-diagram svg")).toBeVisible({ timeout: 30_000 });

    await card.getByRole("button", { name: "Abrir en el panel: Flujo de login" }).click();
    const panel = conversationPanel(page);
    await expect(panel.getByRole("tab", { name: "Artefactos" })).toHaveAttribute("aria-selected", "true");
    const view = panel.getByRole("article", { name: "Flujo de login" });
    await expect(view.locator(".mermaid-diagram svg")).toBeVisible();
    await expect(view).toContainText("Pedido con «Hazme un diagrama de secuencia del login»");
    const download = page.waitForEvent("download");
    await view.getByRole("link", { name: "Descargar" }).click();
    expect((await download).suggestedFilename()).toMatch(/^diagrama-flujo-de-login-.*\.mmd$/);

    await view.getByRole("button", { name: "Ver en el chat" }).click();
    await expect(card).toBeFocused();
    await view.getByRole("button", { name: "Todos los artefactos" }).click();
    await expect(panel.getByRole("list", { name: "Artefactos de esta conversación" }).getByText("Flujo de login")).toBeVisible();
  });

  test("«Nueva conversación» es secundario de 32 px como el buscador, y su atajo abre un chat nuevo", async ({ page }) => {
    await page.goto("/");
    const box = page.getByLabel("Mensaje");
    await box.fill("¿Qué es TaskFlow?");
    await box.press("Enter");
    await expect(page).toHaveURL(/\/c\/[0-9a-f]{32}$/);
    await expect(page.getByTestId("answered-by")).toBeVisible();
    const button = page.locator("#sidebar").getByRole("link", { name: "Nueva conversación", exact: true });
    const search = page.getByRole("searchbox", { name: "Buscar conversaciones" });
    expect(Math.round((await button.boundingBox())!.height)).toBe(32);
    expect(Math.round((await search.boundingBox())!.height)).toBe(32);
    expect(await button.getAttribute("data-variant")).toBe("secondary");
    await page.keyboard.press("ControlOrMeta+Shift+O");
    await expect(page).toHaveURL(/\/$/);
  });
});

test.describe("panel de la conversación: cerrar arrastrando y vista previa (Fase 12.C)", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test("arrastrar el borde del panel por debajo de su mínimo lo cierra y el foco vuelve al botón «Panel»", async ({ page }) => {
    await page.goto("/");
    const panel = await openPanelTab(page, "Documentos");
    const handle = page.getByRole("separator", { name: "Ancho del panel de la conversación" });
    const box = (await handle.boundingBox())!;
    const y = box.y + box.height / 2;
    await page.mouse.move(box.x + box.width / 2, y);
    await page.mouse.down();
    await page.mouse.move(box.x + 300, y, { steps: 6 }); // borde izquierdo: hacia la derecha estrecha
    await expect(handle).toHaveAttribute("data-collapse", "armed");
    await expect.poll(() => panel.evaluate((el) => getComputedStyle(el).opacity)).toBe("0.5");
    await page.mouse.up();
    await expect(panel).toBeHidden();
    await expect(page.getByRole("button", { name: "Panel de la conversación" })).toHaveAttribute("aria-expanded", "false");
    // al reabrirlo vuelve al ancho que tenía, no al mínimo
    await page.getByRole("button", { name: "Panel de la conversación" }).click();
    expect(Math.round((await panel.boundingBox())!.width)).toBe(384);
  });

  test("un documento se previsualiza por fragmentos desde la pestaña Documentos", async ({ page }) => {
    await page.goto("/");
    await page.locator("form [data-attach-input]").setInputFiles(SAMPLE);
    await expect(toast(page, "Documento añadido")).toBeVisible();
    const panel = await openPanelTab(page, "Documentos");
    await panel.getByRole("button", { name: "Ver taskflow.md" }).click();
    const fragments = panel.getByRole("list", { name: "Fragmentos de taskflow.md" });
    await expect(fragments.getByText("Fragmento 1", { exact: false }).first()).toBeVisible();
    await expect(fragments).toContainText("TaskFlow");
    expect(await contrastRatio(fragments.locator("li").first().locator("p").first())).toBeGreaterThanOrEqual(4.5);
    await panel.getByRole("button", { name: "Todos los documentos" }).click();
    await expect(panel.getByRole("button", { name: "Ver taskflow.md" })).toBeVisible();
  });

  test("el chat conserva su ancho mínimo aunque se ensanchen el lateral y el panel", async ({ page }) => {
    await page.goto("/");
    await openPanelTab(page, "Pasos");
    await page.getByRole("separator", { name: "Ancho del panel de conversaciones" }).focus();
    await page.keyboard.press("End");
    await page.getByRole("separator", { name: "Ancho del panel de la conversación" }).focus();
    await page.keyboard.press("End");
    expect(Math.round((await page.locator("main").boundingBox())!.width)).toBeGreaterThanOrEqual(480);
  });
});


test.describe("anchos mínimos sin cortes (revisión del autor)", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test("con el panel y el lateral en su mínimo, las pestañas caben y «Nueva conversación» se lee entero", async ({ page }) => {
    await page.goto("/");
    const panel = await openPanelTab(page, "Documentos");
    await page.getByRole("separator", { name: "Ancho del panel de la conversación" }).focus();
    await page.keyboard.press("Home");
    expect(Math.round((await panel.boundingBox())!.width)).toBe(PANEL_LIMITS.trace.min);
    const list = (await panel.getByRole("tablist").boundingBox())!;
    for (const name of ["Documentos", "Artefactos", "Pasos"]) {
      const tab = panel.getByRole("tab", { name });
      const box = (await tab.boundingBox())!;
      expect(box.x + box.width).toBeLessThanOrEqual(list.x + list.width + 0.5); // dentro de la lista
      expect(await tab.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(true); // texto entero
    }

    await page.getByRole("separator", { name: "Ancho del panel de conversaciones" }).focus();
    await page.keyboard.press("Home");
    const label = page.locator("#sidebar").getByRole("link", { name: "Nueva conversación", exact: true }).locator("span.truncate");
    expect(await label.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(true); // «Nueva conversación» entero
    const button = (await page.locator("#sidebar").getByRole("link", { name: "Nueva conversación", exact: true }).boundingBox())!;
    const collapse = (await page.getByRole("button", { name: "Ocultar conversaciones" }).boundingBox())!;
    expect(collapse.y).toBeGreaterThanOrEqual(button.y + button.height); // el de ocultar va en la fila del título: no se tocan
    expect(await page.getByRole("button", { name: "Ocultar conversaciones" }).evaluate((el) => getComputedStyle(el).backgroundColor)).toBe(
      "rgba(0, 0, 0, 0)",
    );
  });
});
