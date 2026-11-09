import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

/** Severity foreground colours as theme tokens (same palette as the badges); only used as CSS colour values (text, bars, SVG stroke/fill). */
export const COLOR: Record<string, string> = { BAJA: "var(--baja-fg)", MEDIA: "var(--media-fg)", CRITICA: "var(--critica-fg)" };
export const ETIQUETA: Record<string, string> = { BAJA: "Baja", MEDIA: "Media", CRITICA: "Crítica" };

export function Badge({ clase, large = false }: { clase: string; large?: boolean }) {
  return <span className={`badge ${clase.toLowerCase()}${large ? " lg" : ""}`}>{ETIQUETA[clase] ?? clase}</span>;
}

export function clasificar(asi: number): string {
  return asi >= 0.7 ? "CRITICA" : asi >= 0.4 ? "MEDIA" : "BAJA";
}

/** Decimal with comma (es-AR style): 0.844 -> "0,844". */
export const dec = (n: number, d = 3) => n.toFixed(d).replace(".", ",");

const COMPONENTE: Record<string, { art: string; nombre: string }> = {
  frecuencia: { art: "la", nombre: "frecuencia" }, volumen: { art: "el", nombre: "volumen" },
  diversidad: { art: "la", nombre: "diversidad" }, persistencia: { art: "la", nombre: "persistencia" },
};

/** The 1-2 components that contribute most to the ASI (second one only if it is at least half as strong). */
export function dominantes(items: { clave: string; aporte: number }[]): { art: string; nombre: string }[] {
  const orden = [...items].sort((a, b) => b.aporte - a.aporte);
  if (!orden.length || orden[0].aporte <= 0) return [];
  const out = [orden[0]];
  if (orden[1] && orden[1].aporte >= orden[0].aporte * 0.5) out.push(orden[1]);
  return out.map((c) => COMPONENTE[c.clave] ?? { art: "el", nombre: c.clave });
}

export function Estado({ e }: { e: string }) {
  return <span className={`tag estado-${e.toLowerCase()}`}>{e.charAt(0) + e.slice(1).toLowerCase().replace("_", " ")}</span>;
}

export function Card({ titulo, extra, children, className = "" }: { titulo?: string; extra?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`card ${className}`}>
      {(titulo || extra) && (
        <header className="card-h">
          <h2>{titulo}</h2>
          {extra}
        </header>
      )}
      {children}
    </section>
  );
}

export function Barra({ valor, max = 1, color = "var(--accent)" }: { valor: number; max?: number; color?: string }) {
  const pct = Math.max(0, Math.min(100, (valor / (max || 1)) * 100));
  return (
    <div className="barra">
      <div style={{ width: `${pct}%`, background: color }} />
    </div>
  );
}

export const fecha = (iso: string | null) =>
  iso ? new Date(iso).toLocaleString("es-AR", { dateStyle: "short", timeStyle: "medium" }) : "—";
export const hora = (iso: string) => new Date(iso).toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" });
export const num = (n: number) => n.toLocaleString("es-AR");

/** Carga datos y los refresca cada `ms` milisegundos. */
export function usePoll<T>(fn: () => Promise<T>, deps: unknown[], ms = 10000) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const ref = useRef(fn);
  ref.current = fn;
  const load = useCallback(async () => {
    try {
      setData(await ref.current());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    setLoading(true);
    void load();
    if (!ms) return;
    const t = setInterval(() => void load(), ms);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, ms]);
  return { data, error, loading, reload: load };
}

export function Estado404({ error }: { error: string | null }) {
  return error ? <div className="aviso aviso-error">{error}</div> : null;
}
