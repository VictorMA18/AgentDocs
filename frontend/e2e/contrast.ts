import type { Locator } from "@playwright/test";

/**
 * Contraste WCAG del texto de un elemento contra el fondo que tiene realmente detrás.
 *
 * Pinta en un canvas la pila de fondos de sus ancestros y luego el color del texto, y lee los
 * píxeles: así se resuelven OKLCH, HSL, transparencias y tintes como los ve el navegador.
 *
 * En Glass el fondo de la página tiene manchas de color (--app-blob-1/2) y el cristal desenfoca lo
 * que haya debajo: el texto puede quedar sobre el color base o sobre cualquiera de las manchas. Se
 * mide con los tres y se devuelve el peor, que es una cota segura de lo que se ve.
 */
export function contrastRatio(locator: Locator): Promise<number> {
  return locator.evaluate((el) => {
    const nodes: Element[] = [];
    for (let node: Element | null = el; node; node = node.parentElement) nodes.unshift(node);

    // Colores de las manchas en RGB (el navegador resuelve hsl() y calc() al asignarlos a un elemento).
    const rootStyle = getComputedStyle(document.documentElement);
    const blobs = ["--app-blob-1", "--app-blob-2"]
      .map((name) => rootStyle.getPropertyValue(name).trim())
      .filter(Boolean)
      .map((value) => {
        const probe = document.createElement("span");
        probe.style.color = value;
        document.body.append(probe);
        const rgb = getComputedStyle(probe).color;
        probe.remove();
        return rgb;
      });

    const ctx = document.createElement("canvas").getContext("2d", { willReadFrequently: true })!;
    const paint = (color: string) => {
      ctx.fillStyle = color;
      ctx.fillRect(0, 0, 1, 1);
      return Array.from(ctx.getImageData(0, 0, 1, 1).data).slice(0, 3);
    };
    const lum = (rgb: number[]) => {
      const [r, g, b] = rgb.map((v) => {
        const c = v / 255;
        return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
      });
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };

    const ratioOver = (backdrop: string | null) => {
      let bg = paint("#fff");
      for (const node of nodes) {
        bg = paint(getComputedStyle(node).backgroundColor);
        if (backdrop && node === document.body) bg = paint(backdrop); // la mancha va sobre el color del body
      }
      const fg = paint(getComputedStyle(el).color);
      const [hi, lo] = [lum(fg), lum(bg)].sort((a, b) => b - a);
      return (hi + 0.05) / (lo + 0.05);
    };

    return Math.min(ratioOver(null), ...blobs.map(ratioOver));
  });
}
