import { create } from "zustand";

import { maxWidth } from "@/lib/layout";

import { useLayoutStore } from "./layout-store";

/** Ancho mínimo del panel al abrir un artefacto en grande (si el panel es más estrecho, se ensancha). */
const ARTIFACT_PANEL_W = 560;

/** Pestañas del panel de la conversación (Fase 12.C, ADR-033). */
export type PanelTab = "documents" | "artifacts" | "steps";

/** A partir de este ancho el panel va fijo junto al chat; por debajo se abre encima (Sheet). */
export const DOCKED_PANEL_QUERY = "(min-width: 1280px)";

type UiState = {
  /** Lateral de conversaciones en pantallas pequeñas (en escritorio está siempre visible). */
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
  /** Panel de la conversación abierto encima del chat en pantallas estrechas (no se guarda). */
  panelSheetOpen: boolean;
  setPanelSheetOpen: (open: boolean) => void;
  panelTab: PanelTab;
  setPanelTab: (tab: PanelTab) => void;
  /** Artefacto que se ve en grande en la pestaña Artefactos (`null` = la lista). */
  selectedArtifact: string | null;
  selectArtifact: (name: string | null) => void;
  /** Documento que se previsualiza en la pestaña Documentos (`null` = la lista). */
  selectedDocument: string | null;
  selectDocument: (source: string | null) => void;
  /** Abre el panel en una pestaña (fijo en pantallas anchas, encima en las estrechas). */
  openPanel: (tab: PanelTab, artifact?: string) => void;
  /** Botón de la cabecera: abre o cierra el panel. */
  togglePanel: () => void;
};

const docked = () => typeof window !== "undefined" && typeof window.matchMedia === "function" && window.matchMedia(DOCKED_PANEL_QUERY).matches;

export const useUiStore = create<UiState>()((set, get) => ({
  sidebarOpen: false,
  setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
  panelSheetOpen: false,
  setPanelSheetOpen: (panelSheetOpen) => set({ panelSheetOpen }),
  panelTab: "documents",
  setPanelTab: (panelTab) => set({ panelTab }),
  selectedArtifact: null,
  selectArtifact: (selectedArtifact) => set({ selectedArtifact }),
  selectedDocument: null,
  selectDocument: (selectedDocument) => set({ selectedDocument }),
  openPanel: (tab, artifact) => {
    set({ panelTab: tab, ...(artifact !== undefined ? { selectedArtifact: artifact } : {}) });
    if (!docked()) {
      set({ panelSheetOpen: true });
      return;
    }
    const layout = useLayoutStore.getState();
    layout.setPanelOpen(true);
    // un artefacto «en grande» necesita sitio: el panel crece hasta 560 px (sin quitarle al chat su mínimo)
    if (artifact && layout.trace < ARTIFACT_PANEL_W) {
      layout.setWidth("trace", Math.min(ARTIFACT_PANEL_W, maxWidth("trace", layout)));
    }
  },
  togglePanel: () => {
    if (docked()) {
      const layout = useLayoutStore.getState();
      layout.setPanelOpen(!layout.panelOpen);
    } else set({ panelSheetOpen: !get().panelSheetOpen });
  },
}));
