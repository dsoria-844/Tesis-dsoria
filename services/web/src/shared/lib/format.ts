/** Decimal with comma (es-AR style): 0.844 -> "0,844". */
export const dec = (n: number, d = 3) => n.toFixed(d).replace(".", ",");

export const fecha = (iso: string | null) =>
  iso ? new Date(iso).toLocaleString("es-AR", { dateStyle: "short", timeStyle: "medium" }) : "—";
export const hora = (iso: string) => new Date(iso).toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" });
export const num = (n: number) => n.toLocaleString("es-AR");

export function hace(seg: number): string {
  const s = Math.max(0, Math.round(seg));
  if (s < 60) return `hace ${s} s`;
  if (s < 3600) return `hace ${Math.floor(s / 60)} min ${s % 60} s`;
  if (s < 86400) return `hace ${Math.floor(s / 3600)} h ${Math.floor((s % 3600) / 60)} min`;
  return `hace ${Math.floor(s / 86400)} d ${Math.floor((s % 86400) / 3600)} h`;
}
