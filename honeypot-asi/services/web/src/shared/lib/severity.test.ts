import { describe, expect, it } from "vitest";
import { clasificar } from "./severity";

describe("clasificar", () => {
  it.each([
    [0, "BAJA"],
    [0.3999, "BAJA"],
    [0.4, "MEDIA"],
    [0.6999, "MEDIA"],
    [0.7, "CRITICA"],
    [1, "CRITICA"],
  ])("clasificar(%s) -> %s", (asi, esperado) => {
    expect(clasificar(asi)).toBe(esperado);
  });

  // The spec says severity is classified on the value rounded to 3 decimals, which would make
  // 0.6995 -> 0.700 -> CRITICA. The frontend does NOT round: it relies on the API already sending a
  // 3-decimal value. This test pins the current behaviour so a change is noticed.
  it("does not round before classifying (API is expected to send 3-decimal values)", () => {
    expect(clasificar(0.6995)).toBe("MEDIA");
    expect(clasificar(0.69949)).toBe("MEDIA");
  });
});
