import { create } from "zustand";

import { applyLayout, clampWidth, DEFAULT_LAYOUT, LAYOUT_KEY, layoutSchema, type Layout, type PanelId } from "@/lib/layout";

type LayoutState = Layout & {
  /** Lee lo guardado. Se llama después de hidratar: el primer render usa los valores por defecto, como el servidor. */
  load: () => void;
  setWidth: (id: PanelId, value: number) => void;
  /** Pliega el lateral a un riel o lo restaura a su ancho anterior (que se conserva mientras está plegado). */
  setCollapsed: (collapsed: boolean) => void;
};

let animating = 0;

export const useLayoutStore = create<LayoutState>()((set, get) => {
  function persist() {
    const { sidebar, trace, collapsed } = get();
    applyLayout({ sidebar, trace, collapsed });
    try {
      localStorage.setItem(LAYOUT_KEY, JSON.stringify({ sidebar, trace, collapsed }));
    } catch {
      // almacenamiento lleno o bloqueado: vale para esta visita
    }
  }
  return {
    ...DEFAULT_LAYOUT,
    load: () => {
      try {
        set(layoutSchema.parse(JSON.parse(localStorage.getItem(LAYOUT_KEY) ?? "{}")));
      } catch {
        // nada guardado o ilegible: se quedan los de por defecto
      }
    },
    setWidth: (id, value) => {
      set({ [id]: clampWidth(id, value) } as Pick<Layout, PanelId>);
      persist();
    },
    setCollapsed: (collapsed) => {
      if (collapsed === get().collapsed) return;
      // Solo plegar y desplegar animan el ancho (globals.css); cambiarlo con flechas o arrastrando, no.
      const root = document.documentElement;
      root.dataset.sidebarAnimating = "";
      window.clearTimeout(animating);
      animating = window.setTimeout(() => delete root.dataset.sidebarAnimating, 300);
      set({ collapsed });
      persist();
    },
  };
});
