import { afterEach, describe, expect, it, vi } from "vitest";
import { dec, fecha, hace, hora, num } from "./format";

describe("dec", () => {
  it("uses a decimal comma and 3 decimals by default", () => {
    expect(dec(0.844)).toBe("0,844");
    expect(dec(1)).toBe("1,000");
  });
  it("honours a custom number of decimals", () => {
    expect(dec(0.5, 1)).toBe("0,5");
    expect(dec(2, 0)).toBe("2");
  });
});

describe("num", () => {
  it("groups thousands with a dot (es-AR)", () => {
    expect(num(1234567)).toBe("1.234.567");
    expect(num(999)).toBe("999");
  });
});

describe("hace", () => {
  it.each([
    [0, "hace 0 s"],
    [59, "hace 59 s"],
    [60, "hace 1 min 0 s"],
    [125, "hace 2 min 5 s"],
    [3599, "hace 59 min 59 s"],
    [3600, "hace 1 h 0 min"],
    [3 * 3600 + 25 * 60 + 40, "hace 3 h 25 min"],
    [86399, "hace 23 h 59 min"],
    [86400, "hace 1 d 0 h"],
    [2 * 86400 + 5 * 3600 + 59 * 60, "hace 2 d 5 h"],
  ])("hace(%i) -> %s", (seg, esperado) => {
    expect(hace(seg)).toBe(esperado);
  });

  it("clamps negatives to zero and rounds fractions", () => {
    expect(hace(-10)).toBe("hace 0 s");
    expect(hace(59.6)).toBe("hace 1 min 0 s");
  });
});

describe("fecha / hora (time-zone pinned)", () => {
  // TZ is pinned to America/Argentina/Buenos_Aires in vite.config.ts (test runs only).
  afterEach(() => {
    vi.useRealTimers();
  });

  it("fecha returns an em dash for null", () => {
    expect(fecha(null)).toBe("—");
  });

  it("fecha renders es-AR short date with time in the pinned zone", () => {
    // 2025-03-04T15:30:45Z == 12:30:45 in Buenos Aires (UTC-3, no DST)
    const s = fecha("2025-03-04T15:30:45Z");
    expect(s).toContain("4/3/25");
    expect(s).toContain("12:30:45");
  });

  it("hora renders hours and minutes (no seconds) in the pinned zone", () => {
    // es-AR uses a 12-hour clock whose exact suffix depends on ICU data, so only match the clock part.
    expect(hora("2025-03-04T15:30:45Z")).toMatch(/^12:30(?!:)/);
  });
});
