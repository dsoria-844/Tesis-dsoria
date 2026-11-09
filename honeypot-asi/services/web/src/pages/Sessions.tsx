import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, type Pagina, type Sesion, type SesionDetalle } from "../api";
import { Card, Estado404, fecha, num, usePoll } from "../components/ui";

const LIMITE = 10;

type Linea = { t: string; texto: string; clase: string };

function lineasDe(s: SesionDetalle): Linea[] {
  return [
    ...s.intentos.map((i) => ({
      t: i.timestamp_evento, clase: i.autenticado ? "ok" : "mal",
      texto: `login: ${i.usuario_ensayado} / ${i.password_ensayado ?? "(vacía)"}  →  ${i.autenticado ? "ACCESO CONCEDIDO (emulado)" : "rechazado"}`,
    })),
    ...s.comandos.map((c) =>
      c.tipo_evento === "COMANDO"
        ? { t: c.timestamp_evento, clase: "cmd", texto: `root@svr04:~# ${c.comando_tipeado}` }
        : { t: c.timestamp_evento, clase: "art", texto: `[${c.tipo_evento.toLowerCase()}] ${c.url_descarga ?? c.comando_tipeado}` },
    ),
  ].sort((a, b) => a.t.localeCompare(b.t));
}

/** Reproducción de sesión: muestra los eventos en orden, respetando (comprimidas) las pausas reales. */
function Terminal({ s }: { s: SesionDetalle }) {
  const lineas = lineasDe(s);
  const [visibles, setVisibles] = useState(lineas.length);
  const [jugando, setJugando] = useState(false);
  const [vel, setVel] = useState(1);
  const fin = useRef<HTMLDivElement>(null);

  useEffect(() => { setVisibles(lineas.length); setJugando(false); }, [s.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!jugando) return;
    if (visibles >= lineas.length) { setJugando(false); return; }
    const gap = visibles === 0 ? 0 : new Date(lineas[visibles].t).getTime() - new Date(lineas[visibles - 1].t).getTime();
    const espera = Math.min(Math.max(gap, 120), 1500) / vel;   // pausas comprimidas: 0,12 s a 1,5 s
    const id = setTimeout(() => setVisibles((v) => v + 1), espera);
    return () => clearTimeout(id);
  }, [jugando, visibles, vel, lineas.length]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { fin.current?.scrollIntoView({ block: "nearest" }); }, [visibles]);

  const reproducir = () => { if (visibles >= lineas.length) setVisibles(0); setJugando(true); };
  return (
    <div className="term">
      <div className="term-bar">
        <span className="dots"><i /><i /><i /></span>
        <span className="term-titulo">Reproducción de sesión · {s.ip_origen}:{s.puerto_origen ?? "—"} · {s.protocolo}</span>
        <span className="term-ctl">
          {jugando
            ? <button className="btn btn-ghost" onClick={() => setJugando(false)}>⏸ Pausar</button>
            : <button className="btn" onClick={reproducir}>▶ Reproducir</button>}
          <button className="btn btn-ghost" onClick={() => { setJugando(false); setVisibles(0); }}>⏮</button>
          <select value={vel} onChange={(e) => setVel(Number(e.target.value))} aria-label="Velocidad">
            <option value={1}>1×</option><option value={2}>2×</option><option value={4}>4×</option>
          </select>
        </span>
      </div>
      <pre className="tty">
        {lineas.length === 0 && <span className="muted">Sesión sin intentos ni comandos (solo conexión/banner).</span>}
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

export default function Sessions() {
  const [ip, setIp] = useState("");
  const [proto, setProto] = useState("");
  const [conCmd, setConCmd] = useState("");
  const [pag, setPag] = useState(0);
  const [params] = useSearchParams();
  // Deep link from the IP detail page; only accept a UUID so it cannot rewrite the API path.
  const enlace = params.get("sesion");
  const [sel, setSel] = useState<string | null>(
    enlace && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(enlace) ? enlace : null,
  );

  const qs = new URLSearchParams({ limit: String(LIMITE), offset: String(pag * LIMITE) });
  if (ip.trim()) qs.set("ip", ip.trim());
  if (proto) qs.set("protocolo", proto);
  if (conCmd) qs.set("con_comandos", conCmd);
  const lista = usePoll(() => api<Pagina<Sesion>>(`/sessions?${qs}`), [qs.toString()]);
  const det = usePoll(() => (sel ? api<SesionDetalle>(`/sessions/${sel}`) : Promise.resolve(null)), [sel], 0);

  const total = lista.data?.total ?? 0;
  const paginas = Math.max(1, Math.ceil(total / LIMITE));
  const hashes = det.data?.comandos.filter((c) => c.hash_descarga_sha256) ?? [];

  return (
    <>
      <div className="titulo"><h1>Explorador de sesiones y auditoría forense</h1></div>
      <Card>
        <div className="filtros">
          <input placeholder="Filtrar por IP o subred (ej. 203.0.113.0/24)" value={ip} onChange={(e) => { setIp(e.target.value); setPag(0); }} />
          <select value={proto} onChange={(e) => { setProto(e.target.value); setPag(0); }}>
            <option value="">Todos los protocolos</option><option value="SSH">SSH</option><option value="TELNET">Telnet</option>
          </select>
          <select value={conCmd} onChange={(e) => { setConCmd(e.target.value); setPag(0); }}>
            <option value="">Con o sin shell</option><option value="true">Ejecutó comandos</option><option value="false">Sin comandos</option>
          </select>
        </div>
        <Estado404 error={lista.error} />
        <table className="clic">
          <thead><tr><th>Inicio</th><th>IP origen</th><th>Puerto</th><th>Proto.</th><th>Duración</th><th>Intentos</th><th>Comandos</th><th>Acceso</th></tr></thead>
          <tbody>
            {lista.data?.items.map((s) => (
              <tr key={s.id} className={s.id === sel ? "sel" : ""} onClick={() => setSel(s.id)}>
                <td>{fecha(s.fecha_inicio)}</td><td><code>{s.ip_origen}</code></td><td>{s.puerto_origen ?? "—"}</td>
                <td>{s.protocolo}</td><td>{s.duracion_segundos == null ? "activa" : `${s.duracion_segundos} s`}</td>
                <td>{num(s.n_intentos)}</td><td>{s.n_comandos}</td><td>{s.obtuvo_acceso ? "sí" : "no"}</td>
              </tr>
            ))}
            {lista.data?.items.length === 0 && <tr><td colSpan={8} className="muted">No hay sesiones con esos filtros.</td></tr>}
          </tbody>
        </table>
        <div className="pager">
          <button className="btn btn-ghost" disabled={pag === 0} onClick={() => setPag(pag - 1)}>← Anterior</button>
          <span className="muted">Página {pag + 1} de {paginas} · {num(total)} sesiones</span>
          <button className="btn btn-ghost" disabled={pag + 1 >= paginas} onClick={() => setPag(pag + 1)}>Siguiente →</button>
        </div>
      </Card>

      {det.data && (
        <div className="grid2 wide-left">
          <Card titulo={`Visor forense · ${det.data.ip_origen} · ${det.data.protocolo}`}>
            <p className="muted">
              Sensor {det.data.sensor} · sesión {det.data.session_cowrie_id} · {fecha(det.data.fecha_inicio)}
            </p>
            <Terminal s={det.data} />
          </Card>
          <Card titulo="Artefactos interceptados (SHA-256)">
            {hashes.length === 0 && <p className="muted">Esta sesión no descargó ni subió archivos.</p>}
            {hashes.map((h, i) => (
              <div key={i} className="artefacto">
                <small className="muted">{h.url_descarga ?? h.comando_tipeado}</small>
                <code>{h.hash_descarga_sha256}</code>
              </div>
            ))}
            <p className="muted">Solo se registra el hash y los metadatos; nunca se ejecuta el archivo.</p>
          </Card>
        </div>
      )}
    </>
  );
}
