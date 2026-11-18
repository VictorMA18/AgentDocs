import { z } from "zod";

// Anchos ajustables de los paneles (Fase 11.B, ADR-030) y lateral plegado a un riel (Fase 12.A). Se
// guardan en localStorage y se aplican en <html>: variables CSS (--sidebar-w, --trace-w) y los atributos
// data-sidebar="collapsed" y data-panel="open" (panel de la conversación fijo, Fase 12.C). React no pinta
// ni los anchos ni esos estados, así que lo guardado no provoca desajustes de hidratación ni saltos.

export type PanelId = "sidebar" | "trace";

/** Límites en px: el mínimo deja leer los nombres y el máximo no ahoga el chat. */
export const PANEL_LIMITS: Record<PanelId, { min: number; default: number; max: number; cssVar: string }> = {
  sidebar: { min: 242, default: 288, max: 360, cssVar: "--sidebar-w" },
  trace: { min: 360, default: 384, max: 720, cssVar: "--trace-w" }, // 360: caben las tres pestañas del panel con su icono
};

export const LAYOUT_KEY = "techdoc-layout";

/** Ancho del riel de iconos (lateral plegado) y umbral de arrastre por debajo del cual se pliega. */
export const RAIL_WIDTH = 56;
export const COLLAPSE_AT = PANEL_LIMITS.sidebar.min - 64;

const width = (id: PanelId) =>
  z.number().int().catch(PANEL_LIMITS[id].default).transform((n) => clampWidth(id, n));

/** Lo guardado no es de fiar: un ancho inválido o fuera de límites vuelve a su valor por defecto o al límite. */
export const layoutSchema = z.object({
  sidebar: width("sidebar"),
  trace: width("trace"),
  collapsed: z.boolean().catch(false).default(false),
  /** Panel de la conversación abierto junto al chat (solo se ve fijo en pantallas anchas). */
  panelOpen: z.boolean().catch(false).default(false),
});
export type Layout = z.infer<typeof layoutSchema>;
export const DEFAULT_LAYOUT: Layout = layoutSchema.parse({});

/** Ancho mínimo que se le deja siempre al chat (la columna del chat mide como mucho 38rem). */
export const CHAT_MIN = 480;
/** Huecos entre paneles, márgenes y separadores alrededor del chat. */
const CHROME = 48;

/**
 * Ancho máximo de un panel ahora mismo. El del lateral es fijo; el del panel de la conversación además
 * deja al chat al menos CHAT_MIN junto al lateral (o su riel). Nunca baja del mínimo del panel.
 */
export function maxWidth(id: PanelId, layout: Pick<Layout, "sidebar" | "collapsed">): number {
  const { min, max } = PANEL_LIMITS[id];
  if (id === "sidebar" || typeof window === "undefined") return max;
  const sidebar = layout.collapsed ? RAIL_WIDTH : layout.sidebar;
  return Math.max(min, Math.min(max, window.innerWidth - sidebar - CHAT_MIN - CHROME));
}

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

/**
 * Lo mismo para un panel plegable (el lateral): mínimo → por defecto → máximo → plegado → por defecto.
 * Es la alternativa sin arrastre (WCAG 2.5.7) también para plegar.
 */
export function nextCollapsibleStep(id: PanelId, value: number, collapsed: boolean): { width: number; collapsed: boolean } {
  const { default: def, max } = PANEL_LIMITS[id];
  if (collapsed) return { width: def, collapsed: false };
  if (value >= max) return { width: value, collapsed: true };
  return { width: nextPreset(id, value), collapsed: false };
}

export function applyLayout(layout: Layout, root: HTMLElement = document.documentElement) {
  for (const id of Object.keys(PANEL_LIMITS) as PanelId[]) {
    root.style.setProperty(PANEL_LIMITS[id].cssVar, `${layout[id]}px`);
  }
  if (layout.collapsed) root.dataset.sidebar = "collapsed";
  else delete root.dataset.sidebar;
  if (layout.panelOpen) root.dataset.panel = "open";
  else delete root.dataset.panel;
}

/** Script previo a pintar (como el de apariencia): pone los anchos guardados (solo números en límites), el plegado y el panel. */
export function layoutScript(): string {
  const limits = JSON.stringify(PANEL_LIMITS);
  return `(function(){try{var l=${limits};var r=document.documentElement;var s=JSON.parse(localStorage.getItem(${JSON.stringify(LAYOUT_KEY)})||"{}");for(var k in l){var v=s[k];if(typeof v==="number"&&v>=l[k].min&&v<=l[k].max)r.style.setProperty(l[k].cssVar,Math.round(v)+"px")}if(s.collapsed===true)r.setAttribute("data-sidebar","collapsed");if(s.panelOpen===true)r.setAttribute("data-panel","open")}catch(e){}})()`;
}
