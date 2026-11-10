const COMPONENTE: Record<string, { art: string; nombre: string }> = {
  frecuencia: { art: "la", nombre: "frecuencia" },
  volumen: { art: "el", nombre: "volumen" },
  diversidad: { art: "la", nombre: "diversidad" },
  persistencia: { art: "la", nombre: "persistencia" },
};

/** The 1-2 components that contribute most to the ASI (second one only if it is at least half as strong). */
export function dominantes(items: { clave: string; aporte: number }[]): { art: string; nombre: string }[] {
  const orden = [...items].sort((a, b) => b.aporte - a.aporte);
  if (!orden.length || orden[0].aporte <= 0) return [];
  const out = [orden[0]];
  if (orden[1] && orden[1].aporte >= orden[0].aporte * 0.5) out.push(orden[1]);
  return out.map((c) => COMPONENTE[c.clave] ?? { art: "el", nombre: c.clave });
}
