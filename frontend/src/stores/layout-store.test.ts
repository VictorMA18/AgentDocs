import { beforeEach, describe, expect, it } from "vitest";

import { DEFAULT_LAYOUT, LAYOUT_KEY, PANEL_LIMITS } from "@/lib/layout";

import { useLayoutStore } from "./layout-store";

beforeEach(() => {
  localStorage.clear();
  useLayoutStore.setState(DEFAULT_LAYOUT);
  document.documentElement.removeAttribute("data-sidebar");
  document.documentElement.removeAttribute("data-panel");
});

describe("useLayoutStore", () => {
  it("cambia el ancho dentro de los límites, lo aplica en <html> y lo guarda", () => {
    useLayoutStore.getState().setWidth("sidebar", 10_000);
    expect(useLayoutStore.getState().sidebar).toBe(PANEL_LIMITS.sidebar.max);
    expect(document.documentElement.style.getPropertyValue("--sidebar-w")).toBe(`${PANEL_LIMITS.sidebar.max}px`);
    expect(JSON.parse(localStorage.getItem(LAYOUT_KEY)!)).toEqual({
      sidebar: PANEL_LIMITS.sidebar.max,
      trace: 384,
      collapsed: false,
      panelOpen: false,
    });
  });

  it("plegar conserva el ancho para volver a él y lo marca en <html>", () => {
    useLayoutStore.getState().setWidth("sidebar", 320);
    useLayoutStore.getState().setCollapsed(true);
    expect(document.documentElement.dataset.sidebar).toBe("collapsed");
    expect(JSON.parse(localStorage.getItem(LAYOUT_KEY)!)).toMatchObject({ sidebar: 320, collapsed: true });
    useLayoutStore.getState().setCollapsed(false);
    expect(document.documentElement.dataset.sidebar).toBeUndefined();
    expect(useLayoutStore.getState().sidebar).toBe(320);
  });

  it("load() lee lo guardado después de hidratar", () => {
    localStorage.setItem(LAYOUT_KEY, JSON.stringify({ sidebar: 300, trace: 500 }));
    useLayoutStore.getState().load();
    expect(useLayoutStore.getState()).toMatchObject({ sidebar: 300, trace: 500 });
  });

  it("abrir el panel de la conversación lo marca en <html> y lo guarda", () => {
    useLayoutStore.getState().setPanelOpen(true);
    expect(document.documentElement.dataset.panel).toBe("open");
    expect(JSON.parse(localStorage.getItem(LAYOUT_KEY)!)).toMatchObject({ panelOpen: true });
    useLayoutStore.getState().setPanelOpen(false);
    expect(document.documentElement.dataset.panel).toBeUndefined();
  });
});
