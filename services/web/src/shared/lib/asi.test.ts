import { describe, expect, it } from "vitest";
import { dominantes } from "./asi";

describe("dominantes", () => {
  it("returns nothing when no component contributes", () => {
    expect(dominantes([])).toEqual([]);
    expect(dominantes([{ clave: "volumen", aporte: 0 }])).toEqual([]);
  });

  it("returns only the top component when the second is below half of it", () => {
    const r = dominantes([
      { clave: "frecuencia", aporte: 0.05 },
      { clave: "volumen", aporte: 0.2 },
    ]);
    expect(r.map((c) => c.nombre)).toEqual(["volumen"]);
  });

  it("includes the second component at exactly half strength, ordered by contribution", () => {
    const r = dominantes([
      { clave: "persistencia", aporte: 0.1 },
      { clave: "diversidad", aporte: 0.2 },
    ]);
    expect(r.map((c) => c.nombre)).toEqual(["diversidad", "persistencia"]);
  });

  it("falls back to a generic article for unknown keys", () => {
    expect(dominantes([{ clave: "otro", aporte: 1 }])).toEqual([{ art: "el", nombre: "otro" }]);
  });
});
