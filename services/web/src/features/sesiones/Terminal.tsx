import { useEffect, useRef, useState } from "react";
import type { SesionDetalle } from "./types";

type Linea = { t: string; texto: string; clase: string };

function lineasDe(s: SesionDetalle): Linea[] {
  return [
    ...s.intentos.map((i) => ({
      t: i.timestamp_evento,
      clase: i.autenticado ? "ok" : "mal",
      texto: `login: ${i.usuario_ensayado} / ${i.password_ensayado ?? "(vacía)"}  →  ${i.autenticado ? "ACCESO CONCEDIDO (emulado)" : "rechazado"}`,
    })),
    ...s.comandos.map((c) =>
      c.tipo_evento === "COMANDO"
        ? { t: c.timestamp_evento, clase: "cmd", texto: `root@svr04:~# ${c.comando_tipeado}` }
        : {
            t: c.timestamp_evento,
            clase: "art",
            texto: `[${c.tipo_evento.toLowerCase()}] ${c.url_descarga ?? c.comando_tipeado}`,
          },
    ),
  ].sort((a, b) => a.t.localeCompare(b.t));
}

/** Reproducción de sesión: muestra los eventos en orden, respetando (comprimidas) las pausas reales. */
export default function Terminal({ s }: { s: SesionDetalle }) {
  const lineas = lineasDe(s);
  const [visibles, setVisibles] = useState(lineas.length);
  const [jugando, setJugando] = useState(false);
  const [vel, setVel] = useState(1);
  const fin = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setVisibles(lineas.length);
    setJugando(false);
  }, [s.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!jugando) return;
    if (visibles >= lineas.length) {
      setJugando(false);
      return;
    }
    const gap =
      visibles === 0 ? 0 : new Date(lineas[visibles].t).getTime() - new Date(lineas[visibles - 1].t).getTime();
    const espera = Math.min(Math.max(gap, 120), 1500) / vel; // pausas comprimidas: 0,12 s a 1,5 s
    const id = setTimeout(() => setVisibles((v) => v + 1), espera);
    return () => clearTimeout(id);
  }, [jugando, visibles, vel, lineas.length]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    fin.current?.scrollIntoView({ block: "nearest" });
  }, [visibles]);

  const reproducir = () => {
    if (visibles >= lineas.length) setVisibles(0);
    setJugando(true);
  };
  return (
    <div className="term">
      <div className="term-bar">
        <span className="dots">
          <i />
          <i />
          <i />
        </span>
        <span className="term-titulo">
          Reproducción de sesión · {s.ip_origen}:{s.puerto_origen ?? "—"} · {s.protocolo}
        </span>
        <span className="term-ctl">
          {jugando ? (
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setJugando(false)}>
              ⏸ Pausar
            </button>
          ) : (
            <button type="button" className="btn btn-sm" onClick={reproducir}>
              ▶ Reproducir
            </button>
          )}
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => {
              setJugando(false);
              setVisibles(0);
            }}
            aria-label="Volver al inicio"
            title="Volver al inicio"
          >
            ⏮
          </button>
          <select value={vel} onChange={(e) => setVel(Number(e.target.value))} aria-label="Velocidad">
            <option value={1}>1×</option>
            <option value={2}>2×</option>
            <option value={4}>4×</option>
          </select>
        </span>
      </div>
      <pre className="tty">
        {lineas.length === 0 && <span className="tty-t">Sesión sin intentos ni comandos (solo conexión/banner).</span>}
        {lineas.slice(0, visibles).map((l, i) => (
          <div key={i} className={`tty-${l.clase}`}>
            <span className="tty-n">{String(i + 1).padStart(2, " ")}</span>
            <span className="tty-t">{new Date(l.t).toLocaleTimeString("es-AR")}</span> {l.texto}
          </div>
        ))}
        {jugando && <span className="cursor">█</span>}
        <div ref={fin} />
      </pre>
    </div>
  );
}
