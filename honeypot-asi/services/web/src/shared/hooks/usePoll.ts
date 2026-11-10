import { useCallback, useEffect, useRef, useState } from "react";

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
