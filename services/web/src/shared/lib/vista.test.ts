import { afterEach, describe, expect, it, vi } from "vitest";
import { conDesde, leerDesde, limpiarVista, restablecerVista } from "./vista";

afterEach(() => vi.useRealTimers());

describe("limpiarVista / restablecerVista", () => {
  it("stores a per-user marker with the current time and notifies listeners", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2025-03-04T15:30:00.000Z"));
    const h = vi.fn();
    window.addEventListener("hp:vista", h);
    limpiarVista("u1");
    window.removeEventListener("hp:vista", h);
    expect(leerDesde("u1")).toBe("2025-03-04T15:30:00.000Z");
    expect(leerDesde("u2")).toBeNull();
    expect(localStorage.getItem("hp_vista_desde:u1")).toBe("2025-03-04T15:30:00.000Z");
    expect(h).toHaveBeenCalledTimes(1);
  });

  it("restablecerVista removes only that user's marker", () => {
    limpiarVista("u1");
    limpiarVista("u2");
    restablecerVista("u1");
    expect(leerDesde("u1")).toBeNull();
    expect(leerDesde("u2")).not.toBeNull();
  });

  it("falls back to memory when localStorage is blocked", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(() => limpiarVista("u9")).not.toThrow();
    expect(leerDesde("u9")).not.toBeNull();
    vi.restoreAllMocks();
    restablecerVista("u9");
  });
});

describe("conDesde", () => {
  it("leaves the path untouched without a marker", () => {
    expect(conDesde("/a", null)).toBe("/a");
  });
  it("appends with ? or & and encodes the timestamp", () => {
    expect(conDesde("/a", "2025-01-01T00:00:00+00:00")).toBe("/a?desde=2025-01-01T00%3A00%3A00%2B00%3A00");
    expect(conDesde("/a?x=1", "t")).toBe("/a?x=1&desde=t");
  });
});
