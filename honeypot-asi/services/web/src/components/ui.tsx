import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

export const COLOR: Record<string, string> = { BAJA: "var(--ok)", MEDIA: "var(--warn)", CRITICA: "var(--crit)" };
export const ETIQUETA: Record<string, string> = { BAJA: "Baja", MEDIA: "Media", CRITICA: "Crítica" };

export function Badge({ clase }: { clase: string }) {
  return (
    <span className="badge" style={{ color: COLOR[clase], borderColor: COLOR[clase] }}>
      {ETIQUETA[clase] ?? clase}
    </span>
  );
}

export function clasificar(asi: number): string {
  return asi >= 0.7 ? "CRITICA" : asi >= 0.4 ? "MEDIA" : "BAJA";
}

export function Estado({ e }: { e: string }) {
  return <span className={`estado estado-${e.toLowerCase()}`}>{e.replace("_", " ")}</span>;
}

export function Card({ titulo, extra, children, className = "" }: { titulo?: string; extra?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`card ${className}`}>
      {(titulo || extra) && (
        <header className="card-h">
          <h3>{titulo}</h3>
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
