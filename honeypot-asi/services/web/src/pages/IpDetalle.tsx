import { useState, type KeyboardEvent, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  api,
  type AlertasIp,
  type AsiIp,
  type Conteo,
  type CredencialesIp,
  type Pagina,
  type ResumenIp,
  type Sesion,
} from "../api";
import { useAuth } from "../App";
import {
  Badge,
  Barra,
  Card,
  Estado as EstadoTag,
  Estado404,
  COLOR,
  dec,
  dominantes,
  fecha,
  num,
  usePoll,
} from "../components/ui";

const LIMITE = 20;
const NOMBRE = {
  frecuencia: "Frecuencia",
  volumen: "Volumen",
  diversidad: "Diversidad",
  persistencia: "Persistencia",
} as const;

function Top({ titulo, filas }: { titulo: string; filas: Conteo[] }) {
  return (
    <div>
      <h3 className="muted" style={{ marginBottom: 10, fontSize: 13 }}>
        {titulo}
      </h3>
      {filas.length === 0 && <p className="muted">Sin datos.</p>}
      {filas.map((c) => (
        <div key={c.valor} className="fila-cred">
          <code title={c.valor}>{c.valor}</code>
          <span>{c.porcentaje}%</span>
        </div>
      ))}
    </div>
  );
}

function explicacion(u: NonNullable<AsiIp["ultima"]>): ReactNode {
  const dom = dominantes(u.componentes);
  if (!dom.length) return null;
  const en = (c: { art: string; nombre: string }) => (
    <>
      {c.art} <b style={{ color: "var(--ink)" }}>{c.nombre}</b>
    </>
  );
  const lista =
    dom.length === 1 ? (
      en(dom[0])
    ) : (
      <>
        {en(dom[0])} y {en(dom[1])}
      </>
    );
  if (u.clasificacion === "CRITICA") return <>Supera el umbral de 0,70 sobre todo por {lista}.</>;
  if (u.clasificacion === "MEDIA") return <>Está entre 0,40 y 0,70; pesan sobre todo {lista}.</>;
  return <>Está por debajo de 0,40; lo que más pesa es {lista}.</>;
}

function AsiCard({ d }: { d: AsiIp }) {
  const u = d.ultima;
  return (
    <div className="row">
      <section className="card side" style={{ flexBasis: 420 }}>
        <p className="muted" style={{ fontSize: 13 }}>
          Índice de Severidad de Ataque
        </p>
        {!u ? (
          <p className="muted" style={{ marginTop: 8 }}>
            Esta IP todavía no tiene evaluaciones ASI.
          </p>
        ) : (
          <>
            <div className="asi-big">
              <span>{dec(u.puntaje_asi)}</span>
              <Badge clase={u.clasificacion} large />
            </div>
            <p className="muted" style={{ margin: "6px 0 20px", fontSize: 14 }}>
              {explicacion(u)}
            </p>
            <div className="stack" style={{ gap: 14 }}>
              {u.componentes.map((c) => (
                <div key={c.clave} className="comp">
                  <div>
                    <b>{NOMBRE[c.clave]}</b>
                    <small>
                      peso {dec(c.peso, 2)} · aporte {dec(c.aporte)}
                    </small>
                  </div>
                  <Barra valor={c.valor} />
                  <span className="v">{dec(c.valor)}</span>
                </div>
              ))}
            </div>
            <p className="muted" style={{ marginTop: 18, fontSize: 12 }}>
              ASI = suma de valor × peso. Evaluado el {fecha(u.fecha_calculo)} · ventana de{" "}
              {Math.round(u.ventana_segundos / 60)} min · {num(u.n_intentos)} intentos · {num(u.k_pares_distintos)}{" "}
              credenciales distintas.
            </p>
          </>
        )}
      </section>

      <section className="card grow">
        <h2>Evolución del ASI</h2>
        <p className="muted" style={{ fontSize: 13 }}>
          Un punto por cada recálculo del motor (cada 30 s)
        </p>
        <div style={{ height: 250, marginTop: 18 }}>
          <ResponsiveContainer>
            <LineChart data={d.serie} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
              <ReferenceArea y1={0.7} y2={1} fill="var(--critica-bg)" fillOpacity={0.55} />
              <CartesianGrid stroke="var(--line)" vertical={false} />
              <XAxis
                dataKey="fecha_calculo"
                stroke="var(--muted)"
                tick={{ fill: "var(--muted)" }}
                tickLine={false}
                axisLine={{ stroke: "var(--line)" }}
                fontSize={12}
                interval="preserveStartEnd"
                minTickGap={40}
                tickFormatter={(v: string) =>
                  new Date(v).toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" })
                }
              />
              <YAxis
                domain={[0, 1]}
                stroke="var(--muted)"
                tick={{ fill: "var(--muted)" }}
                tickLine={false}
                axisLine={false}
                fontSize={12}
                ticks={[0, 0.4, 0.7, 1]}
                tickFormatter={(v: number) => dec(v, 2)}
              />
              <Tooltip
                labelFormatter={(v: string) => fecha(v)}
                formatter={(v: number) => [dec(v), "ASI"]}
                contentStyle={{
                  background: "var(--surface)",
                  color: "var(--ink)",
                  border: "1px solid var(--line)",
                  borderRadius: 10,
                  fontSize: 13,
                }}
              />
              <ReferenceLine
                y={0.4}
                stroke={COLOR.MEDIA}
                strokeDasharray="4 4"
                label={{
                  value: "Media 0,40",
                  fill: COLOR.MEDIA,
                  fontSize: 11,
                  fontWeight: 600,
                  position: "insideBottomRight",
                }}
              />
              <ReferenceLine
                y={0.7}
                stroke={COLOR.CRITICA}
                strokeDasharray="4 4"
                label={{
                  value: "Crítica 0,70",
                  fill: COLOR.CRITICA,
                  fontSize: 11,
                  fontWeight: 600,
                  position: "insideBottomRight",
                }}
              />
              <Line
                type="monotone"
                dataKey="puntaje_asi"
                stroke="var(--accent)"
                strokeWidth={2.5}
                dot={d.serie.length < 30}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>
    </div>
  );
}

type Pestana = "credenciales" | "sesiones" | "alertas";

function Detalle({ ip }: { ip: string }) {
  const e = encodeURIComponent(ip);
  const [tab, setTab] = useState<Pestana>("credenciales");
  const [pag, setPag] = useState(0);
  const cred = usePoll(() => api<CredencialesIp>(`/ips/${e}/credenciales?limit=10`), [ip], 5000);
  const ses = usePoll(
    () => api<Pagina<Sesion>>(`/ips/${e}/sesiones?limit=${LIMITE}&offset=${pag * LIMITE}`),
    [ip, pag],
    5000,
  );
  const al = usePoll(() => api<AlertasIp>(`/ips/${e}/alertas`), [ip], 5000);
  const totalSes = ses.data?.total ?? 0;
  const paginas = Math.max(1, Math.ceil(totalSes / LIMITE));

  const tabs: { id: Pestana; etiqueta: string; n?: number }[] = [
    { id: "credenciales", etiqueta: "Credenciales" },
    { id: "sesiones", etiqueta: "Sesiones", n: ses.data?.total },
    { id: "alertas", etiqueta: "Alertas", n: al.data?.total },
  ];
  const onKey = (ev: KeyboardEvent) => {
    const i = tabs.findIndex((t) => t.id === tab);
    if (ev.key === "ArrowRight") setTab(tabs[(i + 1) % tabs.length].id);
    else if (ev.key === "ArrowLeft") setTab(tabs[(i + tabs.length - 1) % tabs.length].id);
    else return;
    ev.preventDefault();
  };

  return (
    <section className="card flush">
      <div className="tabs" role="tablist" aria-label="Detalle de la IP" onKeyDown={onKey}>
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            id={`tab-${t.id}`}
            aria-selected={tab === t.id}
            aria-controls={`panel-${t.id}`}
            tabIndex={tab === t.id ? 0 : -1}
            onClick={() => setTab(t.id)}
          >
            {t.etiqueta}
            {t.n != null && (
              <>
                {" "}
                <span className="muted num" style={{ fontWeight: 400 }}>
                  {num(t.n)}
                </span>
              </>
            )}
          </button>
        ))}
      </div>

      <div className="tab-panel" role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
        {tab === "credenciales" && (
          <>
            <Estado404 error={cred.error} />
            {cred.data && (
              <>
                <p className="muted" style={{ marginBottom: 16, fontSize: 13 }}>
                  {num(cred.data.total_intentos)} intentos de login registrados
                </p>
                <div className="grid3">
                  <Top titulo="Usuarios" filas={cred.data.usuarios} />
                  <Top titulo="Contraseñas" filas={cred.data.passwords} />
                  <Top titulo="Pares usuario / contraseña" filas={cred.data.pares} />
                </div>
              </>
            )}
          </>
        )}

        {tab === "sesiones" && (
          <>
            <Estado404 error={ses.error} />
            <div className="tabla-wrap">
              <table style={{ minWidth: 560 }}>
                <thead>
                  <tr>
                    <th>Inicio</th>
                    <th>Duración</th>
                    <th>Proto.</th>
                    <th>Intentos</th>
                    <th>Comandos</th>
                    <th>Acceso</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {ses.data?.items.map((s) => (
                    <tr key={s.id}>
                      <td>{fecha(s.fecha_inicio)}</td>
                      <td className="muted">{s.duracion_segundos == null ? "activa" : `${s.duracion_segundos} s`}</td>
                      <td>{s.protocolo}</td>
                      <td className="num">{num(s.n_intentos)}</td>
                      <td className="num">{s.n_comandos}</td>
                      <td>{s.obtuvo_acceso ? "sí" : "no"}</td>
                      <td>
                        <Link to={`/sesiones?sesion=${s.id}`} style={{ fontWeight: 600 }}>
                          Ver reproducción
                        </Link>
                      </td>
                    </tr>
                  ))}
                  {ses.data?.items.length === 0 && (
                    <tr>
                      <td colSpan={7} className="muted">
                        Sin sesiones registradas.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            <div className="pager">
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                disabled={pag === 0}
                onClick={() => setPag(pag - 1)}
              >
                ← Anterior
              </button>
              <span className="muted">
                Página {pag + 1} de {paginas}
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
            <p className="muted" style={{ marginTop: 12, fontSize: 13 }}>
              Abrí una sesión para reproducirla comando por comando.
            </p>
          </>
        )}

        {tab === "alertas" && (
          <>
            <Estado404 error={al.error} />
            <div className="acciones" style={{ marginTop: 0, justifyContent: "space-between" }}>
              <p className="muted">{al.data?.total ?? 0} alertas e historial de cambios</p>
              <Link to="/alertas" style={{ fontWeight: 600 }}>
                Gestionar en Alertas →
              </Link>
            </div>
            {al.data?.items.length === 0 && (
              <p className="muted" style={{ marginTop: 12 }}>
                Esta IP no generó alertas.
              </p>
            )}
            {al.data?.items.map((a) => (
              <div key={a.id} style={{ marginTop: 18 }}>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
                  <Link to={`/alertas?alerta=${a.id}`} style={{ fontWeight: 600 }}>
                    Alerta #{a.id}
                  </Link>
                  <span className="muted">
                    {fecha(a.fecha_disparo)} · ASI <b style={{ color: "var(--ink)" }}>{dec(a.puntaje_asi)}</b>
                  </span>
                  <EstadoTag e={a.estado_alerta} />
                </div>
                {a.observaciones_auditor && (
                  <p className="muted" style={{ fontSize: 13, marginTop: 4 }}>
                    Observaciones: {a.observaciones_auditor}
                  </p>
                )}
                {a.historial.length === 0 && (
                  <p className="muted" style={{ fontSize: 13, marginTop: 4 }}>
                    Sin cambios de estado.
                  </p>
                )}
                {a.historial.map((h, i) => (
                  <div key={i} className="hist">
                    <span className="hist-t">{fecha(h.fecha)}</span>
                    <span>
                      {h.auditor}: {h.estado_anterior} → <b>{h.estado_nuevo}</b>
                      {h.observaciones_nueva ? ` · “${h.observaciones_nueva}”` : ""}
                    </span>
                  </div>
                ))}
              </div>
            ))}
          </>
        )}
      </div>
    </section>
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
      <div>
        <a
          href="/"
          onClick={(ev) => {
            ev.preventDefault();
            volver();
          }}
          style={{ fontSize: 14, fontWeight: 500 }}
        >
          ← Volver
        </a>
        <div className="ip-title">
          <h1>{ip}</h1>
          {r && r.protocolos.length > 0 && <span className="tag">{r.protocolos.join(" · ")}</span>}
          {r?.alerta_abierta && <span className="tag estado-nueva">Alerta abierta</span>}
        </div>
        {r && (
          <p className="muted" style={{ marginTop: 6 }}>
            {num(r.sesiones)} sesiones · {num(r.intentos_login)} intentos de login ({num(r.intentos_exitosos)} exitosos)
            · {num(r.comandos)} comandos · primer evento {fecha(r.primer_evento)} · último {fecha(r.ultimo_evento)}
          </p>
        )}
      </div>
      <Estado404 error={res.error ?? asi.error} />
      {asi.data ? (
        <AsiCard d={asi.data} />
      ) : (
        <Card>
          <p className="muted">Cargando…</p>
        </Card>
      )}
      {me.rol === "ADMIN_INFRA" ? (
        <div className="aviso">
          Por separación de funciones, el Administrador de Infraestructura no accede a sesiones, credenciales ni
          alertas.
        </div>
      ) : (
        <Detalle ip={ip} />
      )}
    </>
  );
}
