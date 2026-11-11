import { create } from "zustand";

// Paneles laterales en pantallas pequeñas (en escritorio están siempre visibles).
type UiState = {
  sidebarOpen: boolean;
  traceOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
  setTraceOpen: (open: boolean) => void;
};

export const useUiStore = create<UiState>()((set) => ({
  sidebarOpen: false,
  traceOpen: false,
  setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
  setTraceOpen: (traceOpen) => set({ traceOpen }),
}));
