import { create } from "zustand";

import { applyLayout, clampWidth, DEFAULT_LAYOUT, LAYOUT_KEY, layoutSchema, type Layout, type PanelId } from "@/lib/layout";

type LayoutState = Layout & {
  /** Lee lo guardado. Se llama después de hidratar: el primer render usa los valores por defecto, como el servidor. */
  load: () => void;
  setWidth: (id: PanelId, value: number) => void;
};

export const useLayoutStore = create<LayoutState>()((set, get) => ({
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
    const { sidebar, trace } = get();
    applyLayout({ sidebar, trace });
    try {
      localStorage.setItem(LAYOUT_KEY, JSON.stringify({ sidebar, trace }));
    } catch {
      // almacenamiento lleno o bloqueado: el ancho vale para esta visita
    }
  },
}));
