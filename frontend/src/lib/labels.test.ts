import { describe, expect, it } from "vitest";

import { groupByDate } from "./labels";

const now = new Date(2026, 10, 17, 10, 0); // 17/11/2026, 10:00 (hora local)
const at = (day: number, hour = 12) => ({ updated: new Date(2026, 10, day, hour).toISOString(), id: `${day}-${hour}` });

describe("groupByDate", () => {
  it("agrupa por días de calendario en Hoy, Ayer, Últimos 7 días y Anteriores, sin grupos vacíos", () => {
    const groups = groupByDate([at(17, 9), at(16, 23), at(16, 1), at(10), at(9), at(1)], now);
    expect(groups.map((g) => [g.label, g.items.map((i) => i.id)])).toEqual([
      ["Hoy", ["17-9"]],
      ["Ayer", ["16-23", "16-1"]],
      ["Últimos 7 días", ["10-12"]],
      ["Anteriores", ["9-12", "1-12"]],
    ]);
  });

  it("una fecha futura cuenta como hoy y una ilegible como anterior", () => {
    const groups = groupByDate([at(20), { updated: "no es una fecha", id: "x" }], now);
    expect(groups.map((g) => [g.label, g.items.map((i) => i.id)])).toEqual([
      ["Hoy", ["20-12"]],
      ["Anteriores", ["x"]],
    ]);
  });
});
