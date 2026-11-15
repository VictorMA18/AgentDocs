import { create } from "zustand";

import { APPEARANCE_KEY, appearanceSchema, applyAppearance, DEFAULT_APPEARANCE, type Appearance } from "@/lib/appearance";

/** Apariencia actual: la que el script ya dejó en <html> (en el servidor, la de por defecto). */
function readInitial(): Appearance {
  if (typeof document === "undefined") return DEFAULT_APPEARANCE;
  return appearanceSchema.parse({ ...document.documentElement.dataset });
}

/**
 * Aplica un cambio de apariencia sin transiciones: si no, cada color con `transition` (más de cien
 * elementos) se anima a la vez y el cambio se emborrona. Es lo mismo que hace next-themes con
 * `disableTransitionOnChange` al cambiar de tema.
 */
function withoutTransitions(change: () => void) {
  const pause = document.createElement("style");
  pause.textContent = "*,*::before,*::after{transition:none!important}";
  document.head.append(pause);
  change();
  void getComputedStyle(document.body).opacity; // fuerza el recálculo con las transiciones apagadas
  setTimeout(() => pause.remove(), 1);
}

/**
 * Cambia la apariencia con un fundido corto de toda la página (View Transitions API del navegador):
 * se fotografía la página, se aplica el cambio y se funden las dos imágenes, en vez de un salto de
 * colores. `update` debe dejar el DOM ya cambiado al volver (por eso quien llama usa flushSync). Sin
 * soporte o con movimiento reducido, el cambio es inmediato.
 */
export function smoothly(update: () => void) {
  const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  if (!document.startViewTransition || reduce) {
    update();
    return;
  }
  document.startViewTransition(update);
}

type AppearanceState =Appearance & { setAppearance: (patch: Partial<Appearance>) => void };

/**
 * Nada del HTML que se pinta en el servidor depende de este store (el menú solo se abre en el
 * navegador), así que leer el valor real al crearlo no provoca desajustes de hidratación.
 */
export const useAppearanceStore = create<AppearanceState>()((set, get) => ({
  ...readInitial(),
  setAppearance: (patch) => {
    set(patch);
    const { style, tint, font, motion } = get();
    const next = { style, tint, font, motion };
    withoutTransitions(() => applyAppearance(next));
    try {
      localStorage.setItem(APPEARANCE_KEY, JSON.stringify(next));
    } catch {
      // almacenamiento lleno o bloqueado: la elección vale para esta visita
    }
  },
}));
