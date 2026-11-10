import { VISTA_KEY } from "./session";
import type { VistaSerie } from "./types";

export const preferencias = {
  vistaGrafico(): VistaSerie | null {
    try {
      const v = sessionStorage.getItem(VISTA_KEY);
      return v && ["minuto", "hora", "dia", "3d", "5d"].includes(v) ? (v as VistaSerie) : null;
    } catch {
      return null;
    }
  },
  guardarVistaGrafico(v: VistaSerie) {
    try {
      sessionStorage.setItem(VISTA_KEY, v);
    } catch {
      /* storage unavailable */
    }
  },
};
