import path from "node:path";

import { expect, test, type Locator, type Page } from "@playwright/test";

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

  // Pasos del agente (ocultos a primera vista, en un panel que abre la cabecera) y conversación guardada.
  await expect(page.getByRole("list", { name: "Pasos del agente" })).toBeHidden();
  await page.getByRole("button", { name: "Ver los pasos del agente" }).click();
  const trace = page.getByRole("dialog", { name: "Pasos del agente" });
  await expect(trace.getByText("buscar_documentos")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(trace).toBeHidden();
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
      await page.getByRole("button", { name: "Abrir conversaciones y documentos" }).click();
      const shift = await page
        .locator("[data-slot=sheet-content]")
        .evaluate((el) => getComputedStyle(el).getPropertyValue("--tw-enter-translate-x").trim());
      expect(shift).toBe("0");
    });
  });
});

// Apariencia de partida de una prueba: next-themes guarda la luminosidad en "theme" y la app el
// estilo, el tinte y la fuente en "techdoc-appearance" (ADR-029). Se escribe antes de cada carga.
type Look = { theme: "light" | "dark"; style: "classic" | "glass"; font?: "geist" | "dm-sans" };
function startWith(page: Page, { theme, style, font = "geist" }: Look) {
  return page.addInitScript(
    ([t, a]) => {
      localStorage.setItem("theme", t);
      localStorage.setItem("techdoc-appearance", a);
    },
    [theme, JSON.stringify({ style, tint: "neutral", font })] as const,
  );
}

const THEMES: { name: string; look: Look }[] = [
  { name: "Claro", look: { theme: "light", style: "classic" } },
  { name: "Oscuro", look: { theme: "dark", style: "classic" } },
  { name: "Glass con base blanca", look: { theme: "light", style: "glass" } },
  { name: "Glass con base negra", look: { theme: "dark", style: "glass" } },
];

// Texto pequeño: 4,5:1 (WCAG 1.4.3) en los cuatro temas. En Glass el fondo es translúcido: contrastRatio
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

    // texto de éxito al subir un documento (verde sobre su tinte); se quita al final
    const file = `tema-${look.style}-${look.theme}.md`;
    await page.locator("aside input[type=file]").first().setInputFiles({ name: file, mimeType: "text/markdown", buffer: Buffer.from("# Tema\n\nTexto.") });
    const indexed = page.getByText(`${file} indexado`, { exact: false });
    await expect(indexed).toBeVisible();
    await atLeast(indexed);
    await page.getByRole("button", { name: `Quitar ${file}` }).click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Quitar documento" }).click();
    await expect(page.getByRole("list", { name: "Documentos indexados" }).getByText(file, { exact: true })).toBeHidden();

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
    // el compositor va pegado abajo y los mensajes pasan por detrás, pero al final el último queda encima
    await expect(answer.getByTestId("logo-claude")).toBeVisible();
    const [answerBox, panelBox] = await Promise.all([answer.boundingBox(), panel.boundingBox()]);
    expect(answerBox!.y + answerBox!.height).toBeLessThanOrEqual(panelBox!.y);

    // texto secundario de la conversación actual (sobre bg-muted)
    await atLeast(page.locator("aside [aria-current=page] .text-muted-foreground").first());

    // botón destructivo del diálogo de confirmación (capa flotante)
    await page.getByRole("button", { name: /Quitar la conversación/ }).first().click();
    const confirm = page.getByRole("alertdialog").getByRole("button", { name: "Quitar conversación" });
    await expect(confirm).toBeVisible();
    await atLeast(confirm);
    await atLeast(page.locator("[data-slot=alert-dialog-description]"));
    await page.keyboard.press("Escape");

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
  await page.getByRole("button", { name: "Ver los pasos del agente" }).click();
  const trace = page.getByRole("dialog", { name: "Pasos del agente" });
  await expect(trace.getByText("Claude", { exact: true })).toBeVisible();
  await expect(trace.getByText("Gemini", { exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(trace).toBeHidden();

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
