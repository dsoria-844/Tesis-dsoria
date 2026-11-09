import { useState } from "react";
import { Area, AreaChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, preferencias, type ActividadVivo, type Kpi, type Metricas, type Pagina, type SerieOut, type Sesion, type VistaSerie } from "../api";
import { useAuth } from "../App";
import { Link } from "react-router-dom";
import { Badge, Barra, Card, COLOR, Estado404, fecha, num, usePoll } from "../components/ui";
import TablaActividad from "../components/TablaActividad";
import { conDesde, restablecerVista, useDesde } from "../vista";

function Tarjeta({ titulo, k, valor }: { titulo: string; k?: Kpi; valor?: number }) {
  const v = k ? k.valor : valor ?? 0;
  const pct = k?.variacion_pct;
  return (
    <div className="card kpi">
      <span className="muted">{titulo}</span>
      <strong>{num(v)}</strong>
      {k && (
        <small className={pct == null ? "muted" : pct >= 0 ? "sube" : "baja"}>
          {pct == null ? "sin período previo" : `${pct >= 0 ? "▲" : "▼"} ${Math.abs(pct) > 999 ? ">999" : Math.abs(pct)}% vs. período anterior`}
        </small>
      )}
    </div>
  );
}

const VISTAS: { id: VistaSerie; etiqueta: string; titulo: string }[] = [
  { id: "minuto", etiqueta: "Minuto", titulo: "por minuto · última hora" },
  { id: "hora", etiqueta: "Hora", titulo: "por hora · últimas 24 h" },
  { id: "dia", etiqueta: "Día", titulo: "por día · últimos 7 días" },
  { id: "3d", etiqueta: "3 días", titulo: "por hora · últimos 3 días" },
  { id: "5d", etiqueta: "5 días", titulo: "cada 6 horas · últimos 5 días" },
];
const TZ = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";

function etiquetaSerie(iso: string, vista: VistaSerie): string {
  const d = new Date(iso);
  if (vista === "dia") return d.toLocaleDateString("es-AR", { day: "2-digit", month: "2-digit" });
  const h = d.toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit", hour12: false });
  return vista === "3d" || vista === "5d"
    ? `${d.toLocaleDateString("es-AR", { day: "2-digit", month: "2-digit" })} ${h}`
    : h;
}

function etiquetaDetalle(iso: string, vista: VistaSerie): string {
  const d = new Date(iso);
  return vista === "dia"
    ? d.toLocaleDateString("es-AR", { dateStyle: "short" })
    : d.toLocaleString("es-AR", { dateStyle: "short", timeStyle: "short", hour12: false });
}

function ActividadEnVivo({ esInfra, uid }: { esInfra: boolean; uid: string }) {
  // Most recent activity regardless of age (all-time, ordered by last event), not only the last minutes.
  // `desde` is this viewer's "clear view" marker (local to the browser; nothing is deleted).
  const desde = useDesde(uid);
  const v = usePoll(() => api<ActividadVivo>(conDesde("/metrics/live?todo=true&limit=3", desde)), [desde], 3000);
  const d = v.data;
  // "En vivo" only while the latest event is fresh (< 5 min); otherwise the card still shows the latest IPs.
  const ultimo = d?.items[0]?.ultimo_evento;
  const activo = !!(d && ultimo && new Date(d.ahora).getTime() - new Date(ultimo).getTime() < 5 * 60 * 1000);
  return (
    <Card
      titulo="Actividad reciente"
      extra={
        <span style={{ display: "inline-flex", alignItems: "center", gap: 12 }}>
          {activo
            ? <span className="en-vivo"><i className="punto-vivo" aria-hidden="true" />En vivo</span>
            : <span className="muted" style={{ fontSize: 12 }}>Sin ataques en curso</span>}
          <Link to="/actividad" className="btn btn-ghost">Ver todos</Link>
        </span>
      }
    >
      <Estado404 error={v.error} />
      {desde && (
        <p className="muted">
          Vista limpiada el {fecha(desde)} ·{" "}
          <button type="button" className="link-btn" onClick={() => restablecerVista(uid)}>Restablecer</button>
        </p>
      )}
      {d && d.items.length === 0 && desde && <p className="muted">No hay actividad nueva desde que limpiaste la vista.</p>}
      {d && d.items.length === 0 && !desde && (
        <p className="muted">
          {esInfra
            ? "Todavía no se registraron ataques. Lanzá un escenario desde Laboratorio de ataques."
            : "Todavía no se registraron ataques."}
        </p>
      )}
      {d && d.items.length > 0 && (
        <>
          <p className="muted">
            Últimas {d.items.length} IP con actividad · {num(d.total_ips)} IP registradas en total
          </p>
          <TablaActividad items={d.items} ahora={d.ahora} />
        </>
      )}
    </Card>
  );
}

export default function Dashboard() {
  const { me } = useAuth();
  const [horas, setHoras] = useState(24);
  const puedeLeer = me.rol !== "ADMIN_INFRA";
  const m = usePoll(() => api<Metricas>(`/metrics?horas=${horas}`), [horas], 5000);
  const ses = usePoll(
    () => (puedeLeer ? api<Pagina<Sesion>>("/sessions?limit=8") : Promise.resolve(null)),
    [puedeLeer],
  );
  const [vista, setVistaState] = useState<VistaSerie>(() => preferencias.vistaGrafico() ?? "hora");
  const setVista = (v: VistaSerie) => { setVistaState(v); preferencias.guardarVistaGrafico(v); };
  const serie = usePoll(() => api<SerieOut>(`/metrics/serie?vista=${vista}&tz=${encodeURIComponent(TZ)}`), [vista], 5000);
  const d = m.data;
  const vistaInfo = VISTAS.find((x) => x.id === vista)!;

  return (
    <>
      <div className="titulo">
        <h1>Panel general de amenazas</h1>
        <div className="seg">
          {[1, 6, 24, 168].map((h) => (
            <button key={h} className={h === horas ? "on" : ""} onClick={() => setHoras(h)}>
              {h === 168 ? "7 d" : `${h} h`}
            </button>
          ))}
        </div>
      </div>
      <Estado404 error={m.error} />
      {d && (
        <>
          <div className="grid4">
            <Tarjeta titulo="Sesiones capturadas" k={d.sesiones} />
            <Tarjeta titulo="IPs de origen activas" k={d.ips_unicas} />
            <Tarjeta titulo="Intentos de login" k={d.intentos_login} />
            <Tarjeta titulo="Alertas abiertas" valor={d.alertas_abiertas} />
          </div>

          <ActividadEnVivo esInfra={!puedeLeer} uid={me.id} />

          <div className="grid2">
            <Card
              titulo={`Frecuencia de ataques ${vistaInfo.titulo}`}
              extra={
                <div className="seg" role="group" aria-label="Granularidad del gráfico">
                  {VISTAS.map((x) => (
                    <button key={x.id} type="button" className={x.id === vista ? "on" : ""} aria-pressed={x.id === vista}
                      onClick={() => setVista(x.id)}>{x.etiqueta}</button>
                  ))}
                </div>
              }
            >
              <Estado404 error={serie.error} />
              <div style={{ height: 250 }}>
                <ResponsiveContainer>
                  <AreaChart data={serie.data?.serie ?? []} margin={{ top: 8, right: 12, left: -8, bottom: 0 }}>
                    <defs>
                      <linearGradient id="gSsh" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#38bdf8" stopOpacity={0.55} /><stop offset="95%" stopColor="#38bdf8" stopOpacity={0.03} />
                      </linearGradient>
                      <linearGradient id="gTel" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#fb923c" stopOpacity={0.55} /><stop offset="95%" stopColor="#fb923c" stopOpacity={0.03} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="var(--line)" strokeDasharray="3 3" />
                    <XAxis dataKey="hora" tickFormatter={(v: string) => etiquetaSerie(v, vista)} stroke="var(--muted)" fontSize={12} interval="preserveStartEnd" minTickGap={28} />
                    <YAxis stroke="var(--muted)" fontSize={12} allowDecimals={false} label={{ value: "Sesiones", angle: -90, position: "insideLeft", fill: "var(--muted)", fontSize: 12, dx: 14 }} />
                    <Tooltip labelFormatter={(v: string) => etiquetaDetalle(v, vista)} contentStyle={{ background: "var(--panel2)", border: "1px solid var(--line)" }} />
                    <Legend verticalAlign="top" align="right" height={28} />
                    <Area type="monotone" dataKey="ssh" name="SSH" stroke="#38bdf8" strokeWidth={2} fill="url(#gSsh)" />
                    <Area type="monotone" dataKey="telnet" name="Telnet" stroke="#fb923c" strokeWidth={2} fill="url(#gTel)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
              {serie.data && serie.data.serie.every((s) => s.ssh + s.telnet === 0) && <p className="muted">Todavía no hay sesiones en este período.</p>}
            </Card>

            <Card titulo="Top 5 IPs por Índice de Severidad (ASI)">
              {d.top_ips.length === 0 && <p className="muted">Sin evaluaciones todavía.</p>}
              {d.top_ips.map((t) => (
                <div key={t.ip_origen} className="fila-asi">
                  <code>{t.ip_origen}</code>
                  <Barra valor={t.puntaje_asi} color={COLOR[t.clasificacion]} />
                  <strong>{t.puntaje_asi.toFixed(3)}</strong>
                  <Badge clase={t.clasificacion} />
                </div>
              ))}
            </Card>
          </div>

          <div className="grid2">
            <Card titulo="Subredes de origen más activas">
              {d.subredes.length === 0 && <p className="muted">Sin datos.</p>}
              {d.subredes.map((s) => (
                <div key={s.subred} className="fila-asi">
                  <code>{s.subred}</code>
                  <Barra valor={s.sesiones} max={d.subredes[0].sesiones} />
                  <strong>{num(s.sesiones)}</strong>
                </div>
              ))}
            </Card>
            <Card titulo="Latencia del pipeline (última hora)">
              <div className="grid2 tight">
                <div><span className="muted">Escritura del log → base</span><strong className="big">{d.latencias.ingesta_ms == null ? "—" : `${Math.round(d.latencias.ingesta_ms)} ms`}</strong></div>
                <div><span className="muted">Ingesta → veredicto ASI</span><strong className="big">{d.latencias.veredicto_ms == null ? "—" : `${Math.round(d.latencias.veredicto_ms)} ms`}</strong></div>
              </div>
              <p className="muted">Comandos capturados en el período: {num(d.comandos)}</p>
            </Card>
          </div>
        </>
      )}

      {puedeLeer && (
        <Card titulo="Sesiones recientes">
          <table>
            <thead><tr><th>Inicio</th><th>IP origen</th><th>Protocolo</th><th>Intentos</th><th>Comandos</th><th>Acceso</th></tr></thead>
            <tbody>
              {ses.data?.items.map((s) => (
                <tr key={s.id}>
                  <td>{fecha(s.fecha_inicio)}</td><td><code>{s.ip_origen}</code></td><td>{s.protocolo}</td>
                  <td>{num(s.n_intentos)}</td><td>{s.n_comandos}</td>
                  <td>{s.obtuvo_acceso ? <span className="estado estado-nueva">sí</span> : "no"}</td>
                </tr>
              ))}
              {ses.data?.items.length === 0 && <tr><td colSpan={6} className="muted">Sin sesiones todavía.</td></tr>}
            </tbody>
          </table>
        </Card>
      )}
    </>
  );
}
