import type { Locator } from "@playwright/test";

/**
 * Contraste WCAG del texto de un elemento contra el fondo que tiene realmente detrás.
 *
 * Pinta en un canvas la pila de fondos de sus ancestros y luego el color del texto, y lee los
 * píxeles: así se resuelven OKLCH, transparencias y tintes como los ve el navegador.
 */
export function contrastRatio(locator: Locator): Promise<number> {
  return locator.evaluate((el) => {
    const layers: string[] = [];
    for (let node: Element | null = el; node; node = node.parentElement) {
      layers.unshift(getComputedStyle(node).backgroundColor);
    }
    const ctx = document.createElement("canvas").getContext("2d", { willReadFrequently: true })!;
    const paint = (color: string) => {
      ctx.fillStyle = color;
      ctx.fillRect(0, 0, 1, 1);
      return Array.from(ctx.getImageData(0, 0, 1, 1).data).slice(0, 3);
    };
    paint("#fff");
    let bg = [255, 255, 255];
    for (const layer of layers) bg = paint(layer);
    const fg = paint(getComputedStyle(el).color);
    const lum = (rgb: number[]) => {
      const [r, g, b] = rgb.map((v) => {
        const c = v / 255;
        return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
      });
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    const [hi, lo] = [lum(fg), lum(bg)].sort((a, b) => b - a);
    return (hi + 0.05) / (lo + 0.05);
  });
}
