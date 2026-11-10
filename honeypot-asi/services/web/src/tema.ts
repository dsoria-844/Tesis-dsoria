export type Tema = "light" | "dark";
const CLAVE = "hp_tema";

/** Current theme as applied to <html> (set before first paint by the inline script in index.html). */
export function temaActual(): Tema {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

/** Applies and persists the viewer's choice (storage may be unavailable: ignore failures). */
export function fijarTema(t: Tema): void {
  document.documentElement.dataset.theme = t;
  try {
    localStorage.setItem(CLAVE, t);
  } catch {
    /* private mode / blocked storage */
  }
}
