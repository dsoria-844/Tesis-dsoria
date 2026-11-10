import type { ReactNode } from "react";
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
import { dominantes } from "../../shared/lib/asi";
import { dec, fecha, num } from "../../shared/lib/format";
import { COLOR } from "../../shared/lib/severity";
import { Badge } from "../../shared/ui/Badge";
import { Barra } from "../../shared/ui/Barra";
import type { AsiIp } from "./types";

const NOMBRE = {
  frecuencia: "Frecuencia",
  volumen: "Volumen",
  diversidad: "Diversidad",
  persistencia: "Persistencia",
} as const;

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

export default function AsiCard({ d }: { d: AsiIp }) {
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
