import { describe, expect, it, vi } from "vitest";
import { preferencias } from "../../features/dashboard/preferencias";
import { VISTA_KEY, session } from "./session";

describe("session", () => {
  it("stores and reads the token", () => {
    expect(session.token).toBeNull();
    session.set("abc");
    expect(session.token).toBe("abc");
  });

  it("clear() removes the token and the chart-view preference", () => {
    session.set("abc");
    preferencias.guardarVistaGrafico("hora");
    session.clear();
    expect(session.token).toBeNull();
    expect(sessionStorage.getItem(VISTA_KEY)).toBeNull();
    expect(preferencias.vistaGrafico()).toBeNull();
  });
});

describe("preferencias.vistaGrafico", () => {
  it("persists in sessionStorage under hp_vista_grafico", () => {
    preferencias.guardarVistaGrafico("3d");
    expect(sessionStorage.getItem("hp_vista_grafico")).toBe("3d");
    expect(preferencias.vistaGrafico()).toBe("3d");
  });

  it("ignores unknown stored values", () => {
    sessionStorage.setItem(VISTA_KEY, "semana");
    expect(preferencias.vistaGrafico()).toBeNull();
  });

  it("tolerates storage exceptions", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(preferencias.vistaGrafico()).toBeNull();
    expect(() => preferencias.guardarVistaGrafico("dia")).not.toThrow();
  });
});
