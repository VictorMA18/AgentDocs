import { describe, expect, it } from "vitest";

import { findMatch } from "./highlight";

describe("findMatch", () => {
  it("encuentra sin distinguir mayúsculas ni tildes y devuelve posiciones del texto original", () => {
    const text = "¿Cuántos reintentos hace TaskFlow?";
    const [start, end] = findMatch(text, "CUANTOS")!;
    expect(text.slice(start, end)).toBe("Cuántos");
    const [s2, e2] = findMatch(text, "  taskflow ")!;
    expect(text.slice(s2, e2)).toBe("TaskFlow");
  });

  it("devuelve null si no aparece o la búsqueda está vacía", () => {
    expect(findMatch("Diagrama del login", "token")).toBeNull();
    expect(findMatch("Diagrama del login", "   ")).toBeNull();
  });
});
