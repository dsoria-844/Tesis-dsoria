import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, type AlertasIp, type AsiIp, type Conteo, type CredencialesIp, type Pagina, type ResumenIp, type Sesion } from "../api";
import { useAuth } from "../App";
import { Badge, Barra, Card, Estado as EstadoTag, Estado404, COLOR, clasificar, fecha, num, usePoll } from "../components/ui";

const LIMITE = 20;
const NOMBRE = { frecuencia: ["F", "Frecuencia"], volumen: ["V", "Volumen"], diversidad: ["D", "Diversidad"], persistencia: ["P", "Persistencia"] } as const;
const coma = (n: number, d = 2) => n.toFixed(d).replace(".", ",");   // 0.25 -> "0,25"

function Top({ titulo, filas }: { titulo: string; filas: Conteo[] }) {
  return (
    <div>
      <h4>{titulo}</h4>
      {filas.length === 0 && <p className="muted">Sin datos.</p>}
      {filas.map((c) => (
        <div key={c.valor} className="fila-cred">
          <code title={c.valor}>{c.valor}</code>
          <Barra valor={c.porcentaje} max={filas[0].porcentaje || 1} />
          <small>{c.porcentaje}%</small>
        </div>
      ))}
    </div>
  );
}

function AsiDesglosado({ d }: { d: AsiIp }) {
  const u = d.ultima;
  if (!u) return <p className="muted">Esta IP todavía no tiene evaluaciones ASI.</p>;
  return (
    <>
      <p className="muted">
        Última evaluación {fecha(u.fecha_calculo)} · ventana de {Math.round(u.ventana_segundos / 60)} min · {num(u.n_intentos)} intentos · {u.k_pares_distintos} pares distintos
      </p>
      <div className="grid2">
        <div>
          {u.componentes.map((c) => (
            <div key={c.clave} className="fila-asi" style={{ gridTemplateColumns: "1fr 120px 150px" }}>
              <span><b>{NOMBRE[c.clave][0]}</b> <small className="muted">{NOMBRE[c.clave][1]} · peso {coma(c.peso)}</small></span>
              <Barra valor={c.valor} />
              <strong>{c.valor.toFixed(3)} <small className="muted">→ {c.aporte.toFixed(3)}</small></strong>
            </div>
          ))}
          <div className="fila-asi total" style={{ gridTemplateColumns: "1fr 120px 150px" }}>
            <span><b>ASI</b> <Badge clase={u.clasificacion} /></span>
            <Barra valor={u.puntaje_asi} color={COLOR[clasificar(u.puntaje_asi)]} />
            <strong>{u.puntaje_asi.toFixed(3)}</strong>
          </div>
          <p className="muted"><small>Aporte = valor × peso; la suma de los aportes es el ASI.</small></p>
        </div>
        <div style={{ height: 210 }}>
          <ResponsiveContainer>
            <LineChart data={d.serie} margin={{ top: 8, right: 12, left: -16, bottom: 0 }}>
              <CartesianGrid stroke="var(--line)" strokeDasharray="3 3" />
              <XAxis dataKey="fecha_calculo" stroke="var(--muted)" fontSize={11} interval="preserveStartEnd" minTickGap={40}
                     tickFormatter={(v: string) => new Date(v).toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" })} />
              <YAxis domain={[0, 1]} stroke="var(--muted)" fontSize={11} ticks={[0, 0.4, 0.7, 1]} />
              <Tooltip labelFormatter={(v: string) => fecha(v)} formatter={(v: number) => [v.toFixed(3), "ASI"]} contentStyle={{ background: "var(--panel2)", border: "1px solid var(--line)" }} />
              <ReferenceLine y={0.4} stroke={COLOR.MEDIA} strokeDasharray="4 4" label={{ value: "0,40", fill: "var(--muted)", fontSize: 10, position: "insideTopRight" }} />
              <ReferenceLine y={0.7} stroke={COLOR.CRITICA} strokeDasharray="4 4" label={{ value: "0,70", fill: "var(--muted)", fontSize: 10, position: "insideTopRight" }} />
              <Line type="monotone" dataKey="puntaje_asi" stroke="#38bdf8" strokeWidth={2} dot={d.serie.length < 30} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </>
  );
}

function Sesiones({ ip }: { ip: string }) {
  const [pag, setPag] = useState(0);
  const q = usePoll(() => api<Pagina<Sesion>>(`/ips/${encodeURIComponent(ip)}/sesiones?limit=${LIMITE}&offset=${pag * LIMITE}`), [ip, pag], 5000);
  const total = q.data?.total ?? 0;
  const paginas = Math.max(1, Math.ceil(total / LIMITE));
  return (
    <Card titulo={`Sesiones · ${num(total)}`}>
      <Estado404 error={q.error} />
      <table>
        <thead><tr><th>Inicio</th><th>Duración</th><th>Proto.</th><th>Intentos</th><th>Comandos</th><th>Acceso</th><th /></tr></thead>
        <tbody>
          {q.data?.items.map((s) => (
            <tr key={s.id}>
              <td>{fecha(s.fecha_inicio)}</td>
              <td>{s.duracion_segundos == null ? "activa" : `${s.duracion_segundos} s`}</td>
              <td>{s.protocolo}</td><td>{num(s.n_intentos)}</td><td>{s.n_comandos}</td><td>{s.obtuvo_acceso ? "sí" : "no"}</td>
              <td><Link to={`/sesiones?sesion=${s.id}`}>Ver reproducción</Link></td>
            </tr>
          ))}
          {q.data?.items.length === 0 && <tr><td colSpan={7} className="muted">Sin sesiones registradas.</td></tr>}
        </tbody>
      </table>
      <div className="pager">
        <button className="btn btn-ghost" disabled={pag === 0} onClick={() => setPag(pag - 1)}>← Anterior</button>
        <span className="muted">Página {pag + 1} de {paginas}</span>
        <button className="btn btn-ghost" disabled={pag + 1 >= paginas} onClick={() => setPag(pag + 1)}>Siguiente →</button>
      </div>
    </Card>
  );
}

function Detalle({ ip }: { ip: string }) {
  const e = encodeURIComponent(ip);
  const cred = usePoll(() => api<CredencialesIp>(`/ips/${e}/credenciales?limit=10`), [ip], 5000);
  const al = usePoll(() => api<AlertasIp>(`/ips/${e}/alertas`), [ip], 5000);
  return (
    <>
      <Card titulo={`Credenciales probadas · ${num(cred.data?.total_intentos ?? 0)} intentos`}>
        <Estado404 error={cred.error} />
        {cred.data && (
          <div className="grid3">
            <Top titulo="Usuarios" filas={cred.data.usuarios} />
            <Top titulo="Contraseñas" filas={cred.data.passwords} />
            <Top titulo="Pares usuario / contraseña" filas={cred.data.pares} />
          </div>
        )}
      </Card>
      <Sesiones ip={ip} />
      <Card titulo={`Alertas e historial · ${al.data?.total ?? 0}`} extra={<Link to="/alertas">Gestionar en Alertas →</Link>}>
        <Estado404 error={al.error} />
        {al.data?.items.length === 0 && <p className="muted">Esta IP no generó alertas.</p>}
        {al.data?.items.map((a) => (
          <div key={a.id} style={{ marginBottom: 14 }}>
            <div>
              <Link to={`/alertas?alerta=${a.id}`}>Alerta #{a.id}</Link> · {fecha(a.fecha_disparo)} · ASI <b>{a.puntaje_asi.toFixed(3)}</b> · <EstadoTag e={a.estado_alerta} />
            </div>
            {a.observaciones_auditor && <small className="muted">Observaciones: {a.observaciones_auditor}</small>}
            {a.historial.length === 0 && <div><small className="muted">Sin cambios de estado.</small></div>}
            {a.historial.map((h, i) => (
              <div key={i} className="hist">
                <small className="muted">{fecha(h.fecha)} · {h.auditor}</small>
                <div>{h.estado_anterior} → <b>{h.estado_nuevo}</b>{h.observaciones_nueva ? ` · “${h.observaciones_nueva}”` : ""}</div>
              </div>
            ))}
          </div>
        ))}
      </Card>
    </>
  );
}

export default function IpDetalle() {
  const { ip = "" } = useParams();
  const { me } = useAuth();
  const nav = useNavigate();
  const e = encodeURIComponent(ip);
  const res = usePoll(() => api<ResumenIp>(`/ips/${e}/resumen`), [ip], 5000);
  const asi = usePoll(() => api<AsiIp>(`/ips/${e}/asi`), [ip], 5000);
  const volver = () => (window.history.state?.idx > 0 ? nav(-1) : nav("/"));
  const r = res.data;

  return (
    <>
      <div className="titulo">
        <div>
          <a href="/" onClick={(ev) => { ev.preventDefault(); volver(); }}>← Volver</a>
          <h1>Detalle de IP · <code>{ip}</code></h1>
        </div>
      </div>
      <Estado404 error={res.error ?? asi.error} />
      {r && (
        <Card>
          <p style={{ margin: 0 }}>
            Protocolos: <b>{r.protocolos.join(", ") || "—"}</b> · Primer evento: <b>{fecha(r.primer_evento)}</b> · Último evento: <b>{fecha(r.ultimo_evento)}</b>
          </p>
          <p className="muted" style={{ margin: "4px 0 0" }}>
            {num(r.sesiones)} sesiones · {num(r.intentos_login)} intentos de login ({num(r.intentos_exitosos)} exitosos) · {num(r.comandos)} comandos
            {r.alerta_abierta && <> · <span className="estado estado-nueva">Alerta abierta</span></>}
          </p>
        </Card>
      )}
      <Card titulo="Índice de Severidad (ASI) desglosado">
        {asi.data ? <AsiDesglosado d={asi.data} /> : <p className="muted">Cargando…</p>}
      </Card>
      {me.rol === "ADMIN_INFRA"
        ? <div className="aviso">Por separación de funciones, el rol Administrador de Infraestructura no accede al detalle de sesiones, credenciales ni alertas.</div>
        : <Detalle ip={ip} />}
    </>
  );
}
