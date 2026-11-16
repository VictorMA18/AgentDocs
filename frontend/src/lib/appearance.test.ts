import { afterEach, describe, expect, it } from "vitest";

import { APPEARANCE_KEY, appearanceSchema, appearanceScript, DEFAULT_APPEARANCE } from "./appearance";

const root = document.documentElement;
// El script antes de pintar es texto: se ejecuta como lo haría el navegador.
const runScript = () => new Function(appearanceScript())();

afterEach(() => {
  localStorage.clear();
  delete root.dataset.style;
  delete root.dataset.tint;
  delete root.dataset.font;
});

describe("apariencia", () => {
  it("por defecto es Classic, tinte neutro, Geist y fondo en movimiento", () => {
    expect(DEFAULT_APPEARANCE).toEqual({ style: "classic", tint: "neutral", font: "geist", motion: "on" });
  });

  it("un valor guardado inválido vuelve a su valor por defecto sin perder los válidos", () => {
    expect(appearanceSchema.parse({ style: "glass", tint: "fucsia", font: 3, motion: "off" })).toEqual({
      style: "glass",
      tint: "neutral",
      font: "geist",
      motion: "off",
    });
  });

  it("el script pone la apariencia guardada en <html> antes de pintar", () => {
    localStorage.setItem(APPEARANCE_KEY, JSON.stringify({ style: "glass", tint: "blue", font: "dm-sans", motion: "off" }));
    runScript();
    expect(root.dataset).toMatchObject({ style: "glass", tint: "blue", font: "dm-sans", motion: "off" });
  });

  it("el script ignora valores desconocidos y JSON roto", () => {
    localStorage.setItem(APPEARANCE_KEY, JSON.stringify({ style: "<img>", font: "dm-sans" }));
    runScript();
    expect(root.dataset).toMatchObject({ style: "classic", tint: "neutral", font: "dm-sans", motion: "on" });

    localStorage.setItem(APPEARANCE_KEY, "{roto");
    expect(runScript).not.toThrow();
  });
});
