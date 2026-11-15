import { z } from "zod";

// Apariencia de la interfaz (ADR-029): ejes independientes que se escriben como atributos en
// <html> y que el CSS traduce a tokens. La luminosidad (claro/oscuro) NO vive aquí: la lleva
// next-themes con la clase `.dark`; en Glass, base blanca = claro y base negra = oscuro.

export const STYLES = ["classic", "glass"] as const;
/**
 * Color de la interfaz (Fase 11.B, ADR-030): en Clásico tiñe el acento (botones, opción marcada, foco);
 * en Glass tiñe además el fondo y las manchas. Cada uno es solo un tono y una saturación HSL en el CSS.
 */
export const TINTS = ["neutral", "red", "blue", "green", "orange"] as const;
export const FONTS = ["geist", "dm-sans"] as const;
/** Movimiento del fondo de Glass: la mancha central se desplaza despacio («on») o se queda quieta. */
export const MOTIONS = ["on", "off"] as const;

export type AppStyle = (typeof STYLES)[number];
export type Tint = (typeof TINTS)[number];
export type AppFont = (typeof FONTS)[number];
export type BackgroundMotion = (typeof MOTIONS)[number];
export type Appearance = { style: AppStyle; tint: Tint; font: AppFont; motion: BackgroundMotion };

export const APPEARANCE_KEY = "techdoc-appearance";

/** Lo guardado en localStorage no es de fiar (otra versión, edición a mano): cada campo inválido vuelve a su valor por defecto. */
export const appearanceSchema = z.object({
  style: z.enum(STYLES).catch("classic"),
  tint: z.enum(TINTS).catch("neutral"),
  font: z.enum(FONTS).catch("geist"),
  motion: z.enum(MOTIONS).catch("on"),
});

export const DEFAULT_APPEARANCE: Appearance = appearanceSchema.parse({});

/** Escribe los atributos `data-style`, `data-tint`, `data-font` y `data-motion` en <html>. */
export function applyAppearance(appearance: Appearance, root: HTMLElement = document.documentElement) {
  root.dataset.style = appearance.style;
  root.dataset.tint = appearance.tint;
  root.dataset.font = appearance.font;
  root.dataset.motion = appearance.motion;
}

/**
 * Script que se ejecuta antes de pintar (mismo patrón que next-themes): lee la apariencia guardada y
 * pone los atributos en <html>, así no hay parpadeo del estilo por defecto al recargar. Solo acepta
 * valores conocidos; es texto plano porque corre antes de que cargue el JavaScript de la app.
 */
export function appearanceScript(): string {
  const allowed = JSON.stringify({ style: STYLES, tint: TINTS, font: FONTS, motion: MOTIONS });
  return `(function(){try{var a=${allowed};var s=JSON.parse(localStorage.getItem(${JSON.stringify(APPEARANCE_KEY)})||"{}");var r=document.documentElement;for(var k in a){r.dataset[k]=a[k].indexOf(s[k])>-1?s[k]:a[k][0]}}catch(e){}})()`;
}
