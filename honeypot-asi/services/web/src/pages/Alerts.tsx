import { useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { api, type Alerta, type AlertaDetalle, type Conteo, type Credenciales, type Estado, type Pagina } from "../api";
import { useAuth } from "../App";
import { Badge, Barra, Card, Estado as EstadoTag, Estado404, clasificar, COLOR, fecha, num, usePoll } from "../components/ui";

const ESTADOS: Estado[] = ["NUEVA", "EN_REVISION", "ARCHIVADA"];

function Desglose({ a }: { a: Alerta }) {
  const d = a.desglose;
  const filas: [string, string, number][] = [
    ["F", "Frecuencia (intentos/s)", d.frecuencia],
    ["V", "Volumen de intentos", d.volumen],
    ["D", "Diversidad de pares usuario/clave", d.diversidad],
    ["P", "Persistencia en la ventana", d.persistencia],
  ];
  return (
    <>
      <p className="muted">
        {num(d.n_intentos)} intentos · {d.k_pares_distintos} pares distintos · ventana de {Math.round(d.ventana_segundos / 60)} min
      </p>
      {filas.map(([k, nombre, v]) => (
        <div key={k} className="fila-asi">
          <span><b>{k}</b> <small className="muted">{nombre}</small></span>
          <Barra valor={v} />
          <strong>{v.toFixed(3)}</strong>
        </div>
      ))}
      <div className="fila-asi total">
        <span><b>ASI</b></span>
        <Barra valor={a.puntaje_asi} color={COLOR[clasificar(a.puntaje_asi)]} />
        <strong>{a.puntaje_asi.toFixed(3)}</strong>
      </div>
    </>
  );
}

function Resolucion({ id, editable, onGuardado }: { id: number; editable: boolean; onGuardado: () => void }) {
  const det = usePoll(() => api<AlertaDetalle>(`/alerts/${id}`), [id], 0);
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
      await api(`/alerts/${id}`, { method: "PATCH", json: { estado_alerta: estado, observaciones_auditor: obs } });
      setMsg({ ok: true, texto: "Cambios guardados y registrados en el historial." });
      await det.reload();
      onGuardado();
    } catch (err) {
      setMsg({ ok: false, texto: err instanceof Error ? err.message : "Error al guardar" });
    }
  }

  if (!det.data) return <p className="muted">Cargando…</p>;
  return (
    <>
      <Desglose a={det.data} />
      <form onSubmit={guardar} className="form">
        <label>Estado
          <select value={estado} disabled={!editable} onChange={(e) => setEstado(e.target.value as Estado)}>
            {ESTADOS.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
          </select>
        </label>
        <label>Observaciones técnicas
          <textarea rows={4} value={obs} disabled={!editable} onChange={(e) => setObs(e.target.value)} placeholder="Dictamen forense, acciones tomadas…" />
        </label>
        {editable
          ? <button className="btn">Guardar</button>
          : <p className="muted">Tu perfil es de solo lectura: únicamente el Auditor de Seguridad modifica alertas.</p>}
        {msg && <div className={`aviso ${msg.ok ? "aviso-ok" : "aviso-error"}`}>{msg.texto}</div>}
      </form>
      <h4>Historial de cambios</h4>
      {det.data.historial.length === 0 && <p className="muted">Sin cambios todavía.</p>}
      {det.data.historial.map((h, i) => (
        <div key={i} className="hist">
          <small className="muted">{fecha(h.fecha)} · {h.auditor}</small>
          <div>{h.estado_anterior} → <b>{h.estado_nuevo}</b>{h.observaciones_nueva ? ` · “${h.observaciones_nueva}”` : ""}</div>
        </div>
      ))}
    </>
  );
}

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

export default function Alerts() {
  const { me } = useAuth();
  const [estado, setEstado] = useState("");
  const [params] = useSearchParams();
  const [sel, setSel] = useState<number | null>(Number(params.get("alerta")) || null);  // deep link from the IP detail page
  const lista = usePoll(() => api<Pagina<Alerta>>(`/alerts?limit=50${estado ? `&estado=${estado}` : ""}`), [estado]);
  const cred = usePoll(() => api<Credenciales>("/credentials/top?horas=24&limit=8"), []);

  return (
    <>
      <div className="titulo">
        <h1>Centro de gestión de alertas</h1>
        <select value={estado} onChange={(e) => { setEstado(e.target.value); setSel(null); }}>
          <option value="">Todos los estados</option>
          {ESTADOS.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
        </select>
      </div>
      <div className="grid2 wide-left">
        <Card titulo={`Alertas (ASI ≥ 0,70) · ${lista.data?.total ?? 0}`}>
          <Estado404 error={lista.error} />
          <table className="clic">
            <thead><tr><th>Disparo</th><th>IP origen</th><th>ASI</th><th>Nivel</th><th>Estado</th></tr></thead>
            <tbody>
              {lista.data?.items.map((a) => (
                <tr key={a.id} className={a.id === sel ? "sel" : ""} onClick={() => setSel(a.id)}>
                  <td>{fecha(a.fecha_disparo)}</td><td><code>{a.ip_origen}</code></td>
                  <td><b>{a.puntaje_asi.toFixed(3)}</b></td><td><Badge clase="CRITICA" /></td><td><EstadoTag e={a.estado_alerta} /></td>
                </tr>
              ))}
              {lista.data?.items.length === 0 && <tr><td colSpan={5} className="muted">No hay alertas con ese filtro.</td></tr>}
            </tbody>
          </table>
        </Card>
        <Card titulo={sel ? `Desglose del ASI · alerta #${sel}` : "Detalle de la alerta"}>
          {sel
            ? <Resolucion key={sel} id={sel} editable={me.rol === "AUDITOR"} onGuardado={() => void lista.reload()} />
            : <p className="muted">Elegí una alerta de la tabla para ver cómo se calculó su puntaje y gestionarla.</p>}
        </Card>
      </div>

      <Card titulo={`Panel de inteligencia de credenciales · últimas 24 h · ${num(cred.data?.total_intentos ?? 0)} intentos`}>
        {cred.data && (
          <div className="grid3">
            <Top titulo="Usuarios más atacados" filas={cred.data.usuarios} />
            <Top titulo="Contraseñas más probadas" filas={cred.data.passwords} />
            <Top titulo="Pares usuario / contraseña" filas={cred.data.pares} />
          </div>
        )}
      </Card>
    </>
  );
}
