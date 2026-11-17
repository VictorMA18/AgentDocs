import { beforeEach, describe, expect, it } from "vitest";

import {
  applyLayout,
  clampWidth,
  DEFAULT_LAYOUT,
  LAYOUT_KEY,
  layoutSchema,
  layoutScript,
  nextCollapsibleStep,
  nextPreset,
  PANEL_LIMITS,
} from "./layout";

const root = document.documentElement;
beforeEach(() => {
  localStorage.clear();
  root.removeAttribute("style");
  root.removeAttribute("data-sidebar");
});

describe("anchos de los paneles", () => {
  it("por defecto el lateral mide 288 px y el panel de pasos 384 px", () => {
    expect(DEFAULT_LAYOUT).toEqual({ sidebar: 288, trace: 384, collapsed: false });
  });

  it("lo guardado se recorta a los límites y lo ilegible vuelve al valor por defecto", () => {
    expect(layoutSchema.parse({ sidebar: 9999, trace: "ancho", collapsed: "sí" })).toEqual({
      sidebar: PANEL_LIMITS.sidebar.max,
      trace: 384,
      collapsed: false,
    });
    expect(clampWidth("trace", 10)).toBe(PANEL_LIMITS.trace.min);
  });

  it("un clic en el separador pasa por mínimo, por defecto y máximo", () => {
    const { min, default: def, max } = PANEL_LIMITS.sidebar;
    expect(nextPreset("sidebar", min)).toBe(def);
    expect(nextPreset("sidebar", def)).toBe(max);
    expect(nextPreset("sidebar", max)).toBe(min);
  });

  it("en el lateral plegable el clic sigue: mínimo, por defecto, máximo, plegado y por defecto", () => {
    const { min, default: def, max } = PANEL_LIMITS.sidebar;
    expect(nextCollapsibleStep("sidebar", min, false)).toEqual({ width: def, collapsed: false });
    expect(nextCollapsibleStep("sidebar", def, false)).toEqual({ width: max, collapsed: false });
    expect(nextCollapsibleStep("sidebar", max, false)).toEqual({ width: max, collapsed: true });
    expect(nextCollapsibleStep("sidebar", max, true)).toEqual({ width: def, collapsed: false });
  });

  it("el script pone los anchos guardados antes de pintar e ignora los que se salen de los límites", () => {
    localStorage.setItem(LAYOUT_KEY, JSON.stringify({ sidebar: 320, trace: 5000 }));
    new Function(layoutScript())();
    expect(root.style.getPropertyValue("--sidebar-w")).toBe("320px");
    expect(root.style.getPropertyValue("--trace-w")).toBe("");
    expect(root.dataset.sidebar).toBeUndefined();
  });

  it("el plegado guardado se pone antes de pintar y applyLayout lo pone y lo quita", () => {
    localStorage.setItem(LAYOUT_KEY, JSON.stringify({ collapsed: true }));
    new Function(layoutScript())();
    expect(root.dataset.sidebar).toBe("collapsed");
    applyLayout({ ...DEFAULT_LAYOUT, collapsed: false });
    expect(root.dataset.sidebar).toBeUndefined();
  });
});
