import { useEffect, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useAuth } from "../../app/auth/useAuth";
import type { Alerta, Conteo, Estado } from "../../shared/api/types";
import { usePoll } from "../../shared/hooks/usePoll";
import { dominantes } from "../../shared/lib/asi";
import { dec, fecha, hora, num } from "../../shared/lib/format";
import { clasificar, COLOR, ETIQUETA } from "../../shared/lib/severity";
import { Barra } from "../../shared/ui/Barra";
import { Card } from "../../shared/ui/Card";
import { Estado as EstadoTag } from "../../shared/ui/Estado";
import { Estado404 } from "../../shared/ui/Estado404";
import { actualizarAlerta, contarAlertas, listarAlertas, obtenerAlerta, obtenerCredencialesTop } from "./api";

const ESTADOS: Estado[] = ["NUEVA", "EN_REVISION", "ARCHIVADA"];
const ESTADO_TXT: Record<Estado, string> = { NUEVA: "Nueva", EN_REVISION: "En revisión", ARCHIVADA: "Archivada" };
const FILTRO_TXT: Record<Estado, string> = { NUEVA: "Nuevas", EN_REVISION: "En revisión", ARCHIVADA: "Archivadas" };
const PESO = { frecuencia: 0.25, volumen: 0.3, diversidad: 0.2, persistencia: 0.25 } as const;

/** Short reason for the inbox list: the components that weigh most in the score. */
function motivo(a: Alerta): string {
  const d = a.desglose;
  const dom = dominantes(
    (Object.keys(PESO) as (keyof typeof PESO)[]).map((k) => ({ clave: k, aporte: d[k] * PESO[k] })),
  );
  return dom.length ? `por ${dom.map((c) => c.nombre).join(" y ")}` : "ASI alto";
}

function Desglose({ a }: { a: Alerta }) {
  const d = a.desglose;
  const filas: [string, string, number][] = [
    ["F", "Frecuencia (intentos/s)", d.frecuencia],
    ["V", "Volumen de intentos", d.volumen],
    ["D", "Diversidad de pares usuario/clave", d.diversidad],
    ["P", "Persistencia en la ventana", d.persistencia],
  ];
  return (
    <div>
      <p className="sec-t">Desglose del ASI</p>
      <p className="muted" style={{ fontSize: 13, marginBottom: 6 }}>
        {num(d.n_intentos)} intentos · {d.k_pares_distintos} pares distintos · ventana de{" "}
        {Math.round(d.ventana_segundos / 60)} min
      </p>
      {filas.map(([k, nombre, v]) => (
        <div key={k} className="fila-asi">
          <span>
            <b>{k}</b> <small className="muted">{nombre}</small>
          </span>
          <Barra valor={v} />
          <strong className="num" style={{ textAlign: "right" }}>
            {dec(v)}
          </strong>
        </div>
      ))}
    </div>
  );
}

function Resolucion({ id, editable, onGuardado }: { id: number; editable: boolean; onGuardado: () => void }) {
  const det = usePoll(() => obtenerAlerta(id), [id], 0);
  const [estado, setEstado] = useState<Estado>("NUEVA");
  const [obs, setObs] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; texto: string } | null>(null);

  useEffect(() => {
    if (det.data) {
      setEstado(det.data.estado_alerta);
      setObs(det.data.observaciones_auditor ?? "");
      setMsg(null);
    }
  }, [det.data]);

  async function guardar(e: FormEvent) {
    e.preventDefault();
    try {
      await actualizarAlerta(id, estado, obs);
      setMsg({ ok: true, texto: "Cambios guardados y registrados en el historial." });
      await det.reload();
      onGuardado();
    } catch (err) {
      setMsg({ ok: false, texto: err instanceof Error ? err.message : "Error al guardar" });
    }
  }

  if (!det.data) return <p className="muted">{det.error ?? "Cargando…"}</p>;
  const a = det.data;
  const nivel = clasificar(a.puntaje_asi);
  return (
    <>
      <div className="detail-head">
        <div>
          <p className="muted" style={{ fontSize: 13 }}>
            Alerta #{a.id} · {fecha(a.fecha_disparo)}
          </p>
          <h2>{a.ip_origen}</h2>
        </div>
        <div className="detail-asi">
          <span className="num">{dec(a.puntaje_asi)}</span>
          <p style={{ color: COLOR[nivel] }}>{ETIQUETA[nivel]}</p>
        </div>
      </div>

      <Desglose a={a} />

      <form onSubmit={guardar} className="form" style={{ gap: 22 }}>
        <div>
          <p className="sec-t" id={`estado-${id}`}>
            Estado
          </p>
          <div className="seg estado" role="group" aria-labelledby={`estado-${id}`}>
            {ESTADOS.map((s) => (
              <button
                key={s}
                type="button"
                aria-pressed={estado === s}
                disabled={!editable}
                onClick={() => setEstado(s)}
              >
                {ESTADO_TXT[s]}
              </button>
            ))}
          </div>
        </div>
        <label className="campo" style={{ fontWeight: 600 }}>
          Observación del auditor
          <textarea
            rows={3}
            value={obs}
            disabled={!editable}
            onChange={(e) => setObs(e.target.value)}
            placeholder="Qué viste y qué decidiste"
            style={{ fontWeight: 400 }}
          />
        </label>
        {!editable && (
          <p className="muted">
            Vista de solo lectura: solo el Auditor de Seguridad puede cambiar el estado de una alerta.
          </p>
        )}
        <div className="acciones" style={{ marginTop: 0 }}>
          {editable && <button className="btn">Guardar cambios</button>}
          <Link to={`/ip/${encodeURIComponent(a.ip_origen)}`} style={{ fontWeight: 600, fontSize: 14 }}>
            Ver detalle de la IP →
          </Link>
        </div>
        {msg && (
          <div className={`aviso ${msg.ok ? "aviso-ok" : "aviso-error"}`} role="status">
            {msg.texto}
          </div>
        )}
      </form>

      <div className="sec-hist">
        <p className="sec-t">Historial</p>
        {a.historial.length === 0 && (
          <p className="muted" style={{ fontSize: 14 }}>
            Sin cambios de estado todavía.
          </p>
        )}
        {a.historial.map((h, i) => (
          <div key={i} className="hist">
            <span className="hist-t">{hora(h.fecha)}</span>
            <span>
              {h.auditor}: {h.estado_anterior} → <b>{h.estado_nuevo}</b>
              {h.observaciones_nueva ? ` · “${h.observaciones_nueva}”` : ""}
            </span>
          </div>
        ))}
      </div>
    </>
  );
}

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

export default function Alerts() {
  const { me } = useAuth();
  const [estado, setEstado] = useState<Estado | "">("");
  const [params] = useSearchParams();
  const [sel, setSel] = useState<number | null>(Number(params.get("alerta")) || null); // deep link from the IP detail page
  const lista = usePoll(() => listarAlertas(estado), [estado]);
  // Per-state totals for the filter pills (limit=1: only the total is used).
  const conteos = usePoll(
    async () => {
      const r = await Promise.all(ESTADOS.map((s) => contarAlertas(s)));
      return Object.fromEntries(ESTADOS.map((s, i) => [s, r[i].total])) as Record<Estado, number>;
    },
    [],
    10000,
  );
  const cred = usePoll(() => obtenerCredencialesTop(), []);
  const c = conteos.data;
  const todas = c ? ESTADOS.reduce((n, s) => n + c[s], 0) : null;

  const filtros: { id: Estado | ""; txt: string; n: number | null | undefined }[] = [
    { id: "", txt: "Todas", n: todas },
    ...ESTADOS.map((s) => ({ id: s as Estado | "", txt: FILTRO_TXT[s], n: c?.[s] })),
  ];

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Alertas</h1>
          <p>
            IPs que alcanzaron un ASI de 0,70 o más. Revisá cada una, registrá lo que encontraste y archivala al
            resolverla.
          </p>
        </div>
        <div className="pills" role="group" aria-label="Filtrar por estado">
          {filtros.map((f) => (
            <button
              key={f.id || "todas"}
              type="button"
              aria-pressed={estado === f.id}
              onClick={() => {
                setEstado(f.id);
                setSel(null);
              }}
            >
              {f.txt}
              {f.n != null && ` · ${num(f.n)}`}
            </button>
          ))}
        </div>
      </div>

      <div className="row">
        <section className="inbox-list" aria-label="Lista de alertas">
          <Estado404 error={lista.error} />
          {lista.data?.items.map((a) => (
            <button
              key={a.id}
              type="button"
              className="inbox-item"
              aria-current={a.id === sel}
              onClick={() => setSel(a.id)}
            >
              <span className="mono" style={{ fontSize: 14 }}>
                {a.ip_origen}
              </span>
              <b className="num">{dec(a.puntaje_asi)}</b>
              <span className="sub">
                {fecha(a.fecha_disparo)} · {motivo(a)}
              </span>
              <span className="right">
                <EstadoTag e={a.estado_alerta} />
              </span>
            </button>
          ))}
          {lista.data?.items.length === 0 && <p className="inbox-empty">No hay alertas con ese filtro.</p>}
          {lista.data && lista.data.total > lista.data.items.length && (
            <p className="inbox-empty" style={{ fontSize: 13 }}>
              Mostrando las {lista.data.items.length} más recientes de {num(lista.data.total)}.
            </p>
          )}
        </section>

        <section className="card detail" aria-label="Alerta seleccionada">
          {sel ? (
            <Resolucion
              key={sel}
              id={sel}
              editable={me.rol === "AUDITOR"}
              onGuardado={() => {
                void lista.reload();
                void conteos.reload();
              }}
            />
          ) : (
            <p className="muted">Elegí una alerta de la lista para ver cómo se calculó su puntaje y gestionarla.</p>
          )}
        </section>
      </div>

      <Card titulo={`Credenciales más probadas · últimas 24 h · ${num(cred.data?.total_intentos ?? 0)} intentos`}>
        {cred.data && (
          <div className="grid3">
            <Top titulo="Usuarios más probados" filas={cred.data.usuarios} />
            <Top titulo="Contraseñas más probadas" filas={cred.data.passwords} />
            <Top titulo="Pares usuario / contraseña" filas={cred.data.pares} />
          </div>
        )}
      </Card>
    </>
  );
}
