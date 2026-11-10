import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { usePoll } from "../../shared/hooks/usePoll";
import { fecha, num } from "../../shared/lib/format";
import { Card } from "../../shared/ui/Card";
import { Estado404 } from "../../shared/ui/Estado404";
import { listarSesiones, obtenerSesion } from "./api";
import Terminal from "./Terminal";

const LIMITE = 10;

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
  const lista = usePoll(() => listarSesiones(qs), [qs.toString()]);
  const det = usePoll(() => (sel ? obtenerSesion(sel) : Promise.resolve(null)), [sel], 0);

  const total = lista.data?.total ?? 0;
  const paginas = Math.max(1, Math.ceil(total / LIMITE));
  const hashes = det.data?.comandos.filter((c) => c.hash_descarga_sha256) ?? [];

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Sesiones</h1>
          <p>Cada conexión recibida por el honeypot. Elegí una para reproducirla comando por comando.</p>
        </div>
      </div>
      <Card>
        <div className="filtros">
          <input
            aria-label="Filtrar por IP o subred"
            placeholder="Filtrar por IP o subred (ej. 203.0.113.0/24)"
            value={ip}
            onChange={(e) => {
              setIp(e.target.value);
              setPag(0);
            }}
          />
          <select
            aria-label="Protocolo"
            value={proto}
            onChange={(e) => {
              setProto(e.target.value);
              setPag(0);
            }}
          >
            <option value="">Todos los protocolos</option>
            <option value="SSH">SSH</option>
            <option value="TELNET">Telnet</option>
          </select>
          <select
            aria-label="Con o sin comandos"
            value={conCmd}
            onChange={(e) => {
              setConCmd(e.target.value);
              setPag(0);
            }}
          >
            <option value="">Con o sin shell</option>
            <option value="true">Ejecutó comandos</option>
            <option value="false">Sin comandos</option>
          </select>
        </div>
        <Estado404 error={lista.error} />
        <div className="tabla-wrap">
          <table className="clic" style={{ minWidth: 640 }}>
            <thead>
              <tr>
                <th>Inicio</th>
                <th>IP origen</th>
                <th>Puerto</th>
                <th>Proto.</th>
                <th>Duración</th>
                <th>Intentos</th>
                <th>Comandos</th>
                <th>Acceso</th>
              </tr>
            </thead>
            <tbody>
              {lista.data?.items.map((s) => (
                <tr key={s.id} className={s.id === sel ? "sel" : ""} onClick={() => setSel(s.id)}>
                  <td>
                    <button
                      type="button"
                      className="link-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        setSel(s.id);
                      }}
                      aria-label={`Ver sesión del ${fecha(s.fecha_inicio)} desde ${s.ip_origen}`}
                    >
                      {fecha(s.fecha_inicio)}
                    </button>
                  </td>
                  <td>
                    <code>{s.ip_origen}</code>
                  </td>
                  <td className="muted">{s.puerto_origen ?? "—"}</td>
                  <td>{s.protocolo}</td>
                  <td className="muted">{s.duracion_segundos == null ? "activa" : `${s.duracion_segundos} s`}</td>
                  <td className="num">{num(s.n_intentos)}</td>
                  <td className="num">{s.n_comandos}</td>
                  <td>{s.obtuvo_acceso ? "sí" : "no"}</td>
                </tr>
              ))}
              {lista.data?.items.length === 0 && (
                <tr>
                  <td colSpan={8} className="muted">
                    No hay sesiones con esos filtros.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="pager">
          <button type="button" className="btn btn-ghost btn-sm" disabled={pag === 0} onClick={() => setPag(pag - 1)}>
            ← Anterior
          </button>
          <span className="muted">
            Página {pag + 1} de {paginas} · {num(total)} sesiones
          </span>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            disabled={pag + 1 >= paginas}
            onClick={() => setPag(pag + 1)}
          >
            Siguiente →
          </button>
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
            <p className="muted">Se guardan solo el hash y los metadatos: el archivo nunca se ejecuta.</p>
          </Card>
        </div>
      )}
    </>
  );
}
