import { z } from "zod";

// Anchos ajustables de los paneles (Fase 11.B, ADR-030). Se guardan en localStorage y se aplican como
// variables CSS en <html> (--sidebar-w, --trace-w): React no pinta el ancho, así que el valor guardado
// no provoca desajustes de hidratación ni un salto al cargar.

export type PanelId = "sidebar" | "trace";

/** Límites en px: el mínimo deja leer los nombres y el máximo no ahoga el chat. */
export const PANEL_LIMITS: Record<PanelId, { min: number; default: number; max: number; cssVar: string }> = {
  sidebar: { min: 224, default: 288, max: 448, cssVar: "--sidebar-w" },
  trace: { min: 320, default: 384, max: 720, cssVar: "--trace-w" },
};

export const LAYOUT_KEY = "techdoc-layout";

const width = (id: PanelId) =>
  z.number().int().catch(PANEL_LIMITS[id].default).transform((n) => clampWidth(id, n));

/** Lo guardado no es de fiar: un ancho inválido o fuera de límites vuelve a su valor por defecto o al límite. */
export const layoutSchema = z.object({ sidebar: width("sidebar"), trace: width("trace") });
export type Layout = z.infer<typeof layoutSchema>;
export const DEFAULT_LAYOUT: Layout = layoutSchema.parse({});

export function clampWidth(id: PanelId, value: number): number {
  const { min, max } = PANEL_LIMITS[id];
  return Math.round(Math.min(max, Math.max(min, value)));
}

/** El tamaño siguiente al pulsar el separador sin arrastrar: mínimo → por defecto → máximo → mínimo. */
export function nextPreset(id: PanelId, value: number): number {
  const { min, default: def, max } = PANEL_LIMITS[id];
  if (value < def) return def;
  if (value < max) return max;
  return min;
}

export function applyLayout(layout: Layout, root: HTMLElement = document.documentElement) {
  for (const id of Object.keys(PANEL_LIMITS) as PanelId[]) {
    root.style.setProperty(PANEL_LIMITS[id].cssVar, `${layout[id]}px`);
  }
}

/** Script previo a pintar (como el de apariencia): pone los anchos guardados, solo si son números en límites. */
export function layoutScript(): string {
  const limits = JSON.stringify(PANEL_LIMITS);
  return `(function(){try{var l=${limits};var s=JSON.parse(localStorage.getItem(${JSON.stringify(LAYOUT_KEY)})||"{}");for(var k in l){var v=s[k];if(typeof v==="number"&&v>=l[k].min&&v<=l[k].max)document.documentElement.style.setProperty(l[k].cssVar,Math.round(v)+"px")}}catch(e){}})()`;
}
