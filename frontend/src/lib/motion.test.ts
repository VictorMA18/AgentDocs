import { describe, expect, it } from "vitest";

import { ENTER, enterFrom } from "./motion";

describe("entradas con GSAP", () => {
  it("normalmente entran con fundido, 12 px y 4 px de desenfoque", () => {
    expect(enterFrom(false)).toEqual({ opacity: 0, y: ENTER.y, filter: "blur(4px)" });
  });

  it("con movimiento reducido solo hay fundido: nada se desplaza ni se desenfoca", () => {
    expect(enterFrom(true)).toEqual({ opacity: 0 });
  });
});
