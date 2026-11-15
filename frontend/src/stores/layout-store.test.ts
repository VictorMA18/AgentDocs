import { beforeEach, describe, expect, it } from "vitest";

import { DEFAULT_LAYOUT, LAYOUT_KEY, PANEL_LIMITS } from "@/lib/layout";

import { useLayoutStore } from "./layout-store";

beforeEach(() => {
  localStorage.clear();
  useLayoutStore.setState(DEFAULT_LAYOUT);
});

describe("useLayoutStore", () => {
  it("cambia el ancho dentro de los límites, lo aplica en <html> y lo guarda", () => {
    useLayoutStore.getState().setWidth("sidebar", 10_000);
    expect(useLayoutStore.getState().sidebar).toBe(PANEL_LIMITS.sidebar.max);
    expect(document.documentElement.style.getPropertyValue("--sidebar-w")).toBe(`${PANEL_LIMITS.sidebar.max}px`);
    expect(JSON.parse(localStorage.getItem(LAYOUT_KEY)!)).toEqual({ sidebar: PANEL_LIMITS.sidebar.max, trace: 384 });
  });

  it("load() lee lo guardado después de hidratar", () => {
    localStorage.setItem(LAYOUT_KEY, JSON.stringify({ sidebar: 300, trace: 500 }));
    useLayoutStore.getState().load();
    expect(useLayoutStore.getState()).toMatchObject({ sidebar: 300, trace: 500 });
  });
});
