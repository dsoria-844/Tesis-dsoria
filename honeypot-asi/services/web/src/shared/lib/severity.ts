/** Severity foreground colours as theme tokens (same palette as the badges); only used as CSS colour values (text, bars, SVG stroke/fill). */
export const COLOR: Record<string, string> = {
  BAJA: "var(--baja-fg)",
  MEDIA: "var(--media-fg)",
  CRITICA: "var(--critica-fg)",
};
export const ETIQUETA: Record<string, string> = { BAJA: "Baja", MEDIA: "Media", CRITICA: "Crítica" };

export function clasificar(asi: number): string {
  return asi >= 0.7 ? "CRITICA" : asi >= 0.4 ? "MEDIA" : "BAJA";
}
