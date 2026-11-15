import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { APPEARANCE_KEY, DEFAULT_APPEARANCE } from "@/lib/appearance";

import { smoothly, useAppearanceStore } from "./appearance-store";

beforeEach(() => {
  localStorage.clear();
  useAppearanceStore.setState(DEFAULT_APPEARANCE);
});

describe("useAppearanceStore", () => {
  it("al cambiar la apariencia la escribe en <html> y la guarda", () => {
    useAppearanceStore.getState().setAppearance({ style: "glass" });
    useAppearanceStore.getState().setAppearance({ font: "dm-sans" });

    expect(document.documentElement.dataset).toMatchObject({ style: "glass", tint: "neutral", font: "dm-sans", motion: "on" });
    expect(JSON.parse(localStorage.getItem(APPEARANCE_KEY)!)).toEqual({ style: "glass", tint: "neutral", font: "dm-sans", motion: "on" });
  });
});

describe("smoothly", () => {
  const original = window.matchMedia;
  const media = (reduce: boolean) =>
    ((query: string) => ({ matches: reduce && query.includes("reduce"), media: query })) as unknown as typeof window.matchMedia;
  afterEach(() => {
    window.matchMedia = original;
    delete (document as Partial<Document>).startViewTransition;
  });

  it("funde el cambio con la View Transitions API cuando existe", () => {
    window.matchMedia = media(false);
    const start = vi.fn((update: () => void) => update());
    document.startViewTransition = start as unknown as Document["startViewTransition"];
    const update = vi.fn();
    smoothly(update);
    expect(start).toHaveBeenCalledWith(update);
    expect(update).toHaveBeenCalledOnce();
  });

  it("con movimiento reducido (o sin soporte) cambia al instante", () => {
    window.matchMedia = media(true);
    const start = vi.fn();
    document.startViewTransition = start as unknown as Document["startViewTransition"];
    const update = vi.fn();
    smoothly(update);
    expect(start).not.toHaveBeenCalled();
    expect(update).toHaveBeenCalledOnce();
  });
});
