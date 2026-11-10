import { useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, preferencias, type ActividadVivo, type Kpi, type Metricas, type SerieOut, type VistaSerie } from "../api";
import { useAuth } from "../App";
import { Link } from "react-router-dom";
import { Badge, Barra, Card, dec, Estado404, fecha, num, usePoll } from "../components/ui";
import TablaActividad, { hace } from "../components/TablaActividad";
import { conDesde, restablecerVista, useDesde } from "../vista";

function Tarjeta({ titulo, k }: { titulo: string; k: Kpi }) {
  const pct = k.variacion_pct;
  return (
    <div className="kpi">
      <p>{titulo}</p>
      <strong className="num">{num(k.valor)}</strong>
      <small className={pct == null ? "" : pct >= 0 ? "sube" : "baja"}>
        {pct == null
          ? "sin período previo"
          : `${pct >= 0 ? "▲" : "▼"} ${Math.abs(pct) > 999 ? ">999" : Math.abs(pct)}% vs. período anterior`}
      </small>
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

function ActividadEnVivo({ esInfra, uid, compacto = false }: { esInfra: boolean; uid: string; compacto?: boolean }) {
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
      className={compacto ? "side" : ""}
      extra={
        <span style={{ display: "inline-flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
          {activo ? (
            <span className="en-vivo">
              <i className="punto-vivo" aria-hidden="true" />
              En vivo
            </span>
          ) : (
            <span className="muted" style={{ fontSize: 12 }}>
              Sin ataques en curso
            </span>
          )}
          <Link to="/actividad" style={{ fontWeight: 600, fontSize: 14 }}>
            {compacto ? "Ver todo →" : "Ver toda la actividad →"}
          </Link>
        </span>
      }
    >
      <Estado404 error={v.error} />
      {desde && (
        <p className="muted" style={{ marginBottom: 8 }}>
          Vista limpiada el {fecha(desde)} ·{" "}
          <button type="button" className="link-btn" onClick={() => restablecerVista(uid)}>
            Restablecer
          </button>
        </p>
      )}
      {d && d.items.length === 0 && desde && (
        <p className="muted">No hay actividad nueva desde que limpiaste la vista.</p>
      )}
      {d && d.items.length === 0 && !desde && (
        <p className="muted">
          {esInfra
            ? "Todavía no se registraron ataques. Lanzá un escenario desde Laboratorio."
            : "Todavía no se registraron ataques."}
        </p>
      )}
      {d && d.items.length > 0 && (
        <>
          <p className="muted" style={{ fontSize: 13 }}>
            Últimas {d.items.length} IP con actividad · {num(d.total_ips)} IP registradas en total
          </p>
          {compacto ? (
            d.items.map((a) => (
              <Link key={a.ip_origen} to={`/ip/${encodeURIComponent(a.ip_origen)}`} className="top-ip">
                <span style={{ flex: "1 1 auto", minWidth: 0 }}>
                  <span className="mono" style={{ display: "block" }}>
                    {a.ip_origen}
                  </span>
                  <small className="muted">
                    {hace((new Date(d.ahora).getTime() - new Date(a.ultimo_evento).getTime()) / 1000)} ·{" "}
                    {num(a.intentos_login)} intentos
                  </small>
                </span>
                {a.puntaje_asi != null && a.clasificacion ? (
                  <>
                    <b>{dec(a.puntaje_asi)}</b>
                    <Badge clase={a.clasificacion} />
                  </>
                ) : (
                  <span className="muted">—</span>
                )}
              </Link>
            ))
          ) : (
            <TablaActividad items={d.items} ahora={d.ahora} />
          )}
        </>
      )}
    </Card>
  );
}

const PERIODOS = [1, 6, 24, 168];
const periodoTxt = (h: number) => (h === 168 ? "7 días" : h === 1 ? "1 hora" : `${h} horas`);

export default function Dashboard() {
  const { me } = useAuth();
  const [horas, setHoras] = useState(24);
  const puedeLeer = me.rol !== "ADMIN_INFRA";
  const m = usePoll(() => api<Metricas>(`/metrics?horas=${horas}`), [horas], 5000);
  const [vista, setVistaState] = useState<VistaSerie>(() => preferencias.vistaGrafico() ?? "hora");
  const setVista = (v: VistaSerie) => {
    setVistaState(v);
    preferencias.guardarVistaGrafico(v);
  };
  const serie = usePoll(
    () => api<SerieOut>(`/metrics/serie?vista=${vista}&tz=${encodeURIComponent(TZ)}`),
    [vista],
    5000,
  );
  const d = m.data;
  const vistaInfo = VISTAS.find((x) => x.id === vista)!;
  const vacia = !!serie.data && serie.data.serie.every((s) => s.ssh + s.telnet === 0);

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Resumen</h1>
          <p>Últimas {periodoTxt(horas)} · se actualiza cada 5 segundos</p>
        </div>
        <div className="seg" role="group" aria-label="Período">
          {PERIODOS.map((h) => (
            <button key={h} type="button" aria-pressed={h === horas} onClick={() => setHoras(h)}>
              {h === 168 ? "7 d" : `${h} h`}
            </button>
          ))}
        </div>
      </div>
      <Estado404 error={m.error} />
      {d && (
        <>
          <div className="kpis">
            <Tarjeta titulo="Sesiones capturadas" k={d.sesiones} />
            <Tarjeta titulo="IPs de origen activas" k={d.ips_unicas} />
            <Tarjeta titulo="Intentos de login" k={d.intentos_login} />
            <div className={`kpi${d.alertas_abiertas > 0 ? " kpi-alerta" : ""}`}>
              <p>Alertas críticas abiertas</p>
              <strong className="num">{num(d.alertas_abiertas)}</strong>
              {puedeLeer && (
                <small>
                  <Link to="/alertas">Revisar →</Link>
                </small>
              )}
            </div>
          </div>
          <p className="kpi-nota">
            Una IP genera alerta cuando su ASI alcanza 0,70. Para evitar duplicados, no se vuelve a alertar sobre la
            misma IP durante 1 hora.
          </p>

          <div className="row row-chart">
            <section className="card grow">
              <div className="card-h" style={{ marginBottom: 0 }}>
                <div>
                  <h2>Ataques en el tiempo</h2>
                  <p className="muted" style={{ fontSize: 13 }}>
                    Sesiones {vistaInfo.titulo}
                  </p>
                </div>
                <div className="seg soft" role="group" aria-label="Agrupar por">
                  {VISTAS.map((x) => (
                    <button key={x.id} type="button" aria-pressed={x.id === vista} onClick={() => setVista(x.id)}>
                      {x.etiqueta}
                    </button>
                  ))}
                </div>
              </div>
              <div className="leyenda" aria-hidden="true">
                <span>
                  <i style={{ background: "var(--accent)" }} />
                  SSH
                </span>
                <span>
                  <i style={{ background: "var(--telnet)" }} />
                  Telnet
                </span>
              </div>
              <Estado404 error={serie.error} />
              <div style={{ height: 210 }}>
                <ResponsiveContainer>
                  <BarChart
                    data={serie.data?.serie ?? []}
                    margin={{ top: 8, right: 4, left: -16, bottom: 0 }}
                    barCategoryGap="18%"
                  >
                    <CartesianGrid stroke="var(--line)" vertical={false} />
                    <XAxis
                      dataKey="hora"
                      tickFormatter={(v: string) => etiquetaSerie(v, vista)}
                      stroke="var(--muted)"
                      tick={{ fill: "var(--muted)" }}
                      tickLine={false}
                      axisLine={{ stroke: "var(--line)" }}
                      fontSize={12}
                      interval="preserveStartEnd"
                      minTickGap={28}
                    />
                    <YAxis
                      stroke="var(--muted)"
                      tick={{ fill: "var(--muted)" }}
                      tickLine={false}
                      axisLine={false}
                      fontSize={12}
                      allowDecimals={false}
                    />
                    <Tooltip
                      cursor={{ fill: "var(--bg)" }}
                      labelFormatter={(v: string) => etiquetaDetalle(v, vista)}
                      contentStyle={{
                        background: "var(--surface)",
                        color: "var(--ink)",
                        border: "1px solid var(--line)",
                        borderRadius: 10,
                        fontSize: 13,
                      }}
                    />
                    <Bar dataKey="telnet" name="Telnet" stackId="s" fill="var(--telnet)" isAnimationActive={false} />
                    <Bar
                      dataKey="ssh"
                      name="SSH"
                      stackId="s"
                      fill="var(--accent)"
                      radius={[3, 3, 0, 0]}
                      isAnimationActive={false}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              {vacia && (
                <p className="muted" style={{ marginTop: 8 }}>
                  Todavía no hay sesiones en este período.
                </p>
              )}
            </section>

            <ActividadEnVivo compacto esInfra={!puedeLeer} uid={me.id} />
          </div>
        </>
      )}

      {d && (
        <div className="grid3">
          <Card titulo="IPs con mayor severidad">
            <p className="muted" style={{ fontSize: 13, margin: "-6px 0 10px" }}>
              Ordenadas por Índice de Severidad de Ataque (ASI)
            </p>
            {d.top_ips.length === 0 && <p className="muted">El motor todavía no calculó ningún ASI.</p>}
            {d.top_ips.map((t) => (
              <Link key={t.ip_origen} to={`/ip/${encodeURIComponent(t.ip_origen)}`} className="top-ip">
                <span className="mono">{t.ip_origen}</span>
                <b>{dec(t.puntaje_asi)}</b>
                <Badge clase={t.clasificacion} />
              </Link>
            ))}
          </Card>
          <Card titulo="Subredes de origen más activas">
            {d.subredes.length === 0 && <p className="muted">Sin datos.</p>}
            {d.subredes.map((s) => (
              <div key={s.subred} className="fila-asi">
                <code>{s.subred}</code>
                <Barra valor={s.sesiones} max={d.subredes[0].sesiones} />
                <strong className="num">{num(s.sesiones)}</strong>
              </div>
            ))}
          </Card>
          <Card titulo="Tiempos de procesamiento (última hora)">
            <div className="grid2" style={{ gap: 12 }}>
              <div>
                <span className="muted" style={{ fontSize: 13 }}>
                  Del log a la base de datos
                </span>
                <strong className="big num">
                  {d.latencias.ingesta_ms == null ? "—" : `${Math.round(d.latencias.ingesta_ms)} ms`}
                </strong>
              </div>
              <div>
                <span className="muted" style={{ fontSize: 13 }}>
                  Del registro al cálculo del ASI
                </span>
                <strong className="big num">
                  {d.latencias.veredicto_ms == null ? "—" : `${Math.round(d.latencias.veredicto_ms)} ms`}
                </strong>
              </div>
            </div>
            <p className="muted" style={{ marginTop: 12, fontSize: 13 }}>
              Comandos capturados en el período: {num(d.comandos)}
            </p>
          </Card>
        </div>
      )}
    </>
  );
}
