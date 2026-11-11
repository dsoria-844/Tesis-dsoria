import { useEffect, useState } from "react";

// Per-viewer "clear recent activity" marker. It only hides older activity in this browser; nothing is deleted.
const key = (uid: string) => `hp_vista_desde:${uid}`;
const EVT = "hp:vista";
const memoria = new Map<string, string>(); // fallback when localStorage is unavailable

export function leerDesde(uid: string): string | null {
  try {
    return localStorage.getItem(key(uid));
  } catch {
    return memoria.get(uid) ?? null;
  }
}

export function limpiarVista(uid: string): void {
  const ahora = new Date().toISOString();
  memoria.set(uid, ahora);
  try {
    localStorage.setItem(key(uid), ahora);
  } catch {
    /* storage blocked: in-memory fallback */
  }
  window.dispatchEvent(new Event(EVT));
}

export function restablecerVista(uid: string): void {
  memoria.delete(uid);
  try {
    localStorage.removeItem(key(uid));
  } catch {
    /* storage blocked */
  }
  window.dispatchEvent(new Event(EVT));
}

/** Current "desde" ISO timestamp for the user (or null), kept in sync across components and tabs. */
export function useDesde(uid: string): string | null {
  const [desde, setDesde] = useState<string | null>(() => leerDesde(uid));
  useEffect(() => {
    const h = () => setDesde(leerDesde(uid));
    h();
    window.addEventListener(EVT, h);
    window.addEventListener("storage", h);
    return () => {
      window.removeEventListener(EVT, h);
      window.removeEventListener("storage", h);
    };
  }, [uid]);
  return desde;
}

export const conDesde = (path: string, desde: string | null): string =>
  desde ? `${path}${path.includes("?") ? "&" : "?"}desde=${encodeURIComponent(desde)}` : path;
