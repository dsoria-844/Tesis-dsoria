import { useEffect, useState } from "react";
import { api, type LabCatalogo, type LabEscenario, type LabEstado } from "../api";
import { Badge, Barra, Card, Estado404, usePoll } from "../components/ui";
import "./lab.css";

const ESTADO: Record<LabEstado["estado"], string> = {
  idle: "Inactivo", running: "En ejecución", stopping: "Deteniendo…",
  finished: "Finalizado", stopped: "Detenido", error: "Error",
};

type Valores = { count: string; rate: string; tasks: string };

interface Meta {
  titulo: string; resumen: string; esperado: string[]; herramienta: string; protocolo: string;
}

const META: Record<string, Meta> = {
  "banner": { titulo: "Captura de banner", resumen: "Conecta por SSH y lee el banner, sin iniciar sesión.", esperado: ["BAJA"], herramienta: "Script propio", protocolo: "SSH" },
  "nmap-reconocimiento": { titulo: "Escaneo con Nmap", resumen: "Escanea puertos y versiones de SSH y Telnet, sin login.", esperado: ["BAJA"], herramienta: "Nmap", protocolo: "SSH + Telnet" },
  "manual": { titulo: "Login manual", resumen: "Unos pocos intentos de acceso, como una persona que se equivoca.", esperado: ["BAJA"], herramienta: "Script propio", protocolo: "SSH" },
  "rafaga": { titulo: "Ráfaga breve", resumen: "Decenas de intentos rápidos en pocos segundos.", esperado: ["MEDIA"], herramienta: "Script propio", protocolo: "SSH" },
  "persistente": { titulo: "Fuerza bruta persistente", resumen: "Intentos sostenidos durante varios minutos.", esperado: ["CRITICA"], herramienta: "Script propio", protocolo: "SSH" },
  "sigilosa": { titulo: "Fuerza bruta sigilosa", resumen: "Un intento cada 20–40 s para evadir la detección (low and slow).", esperado: ["MEDIA", "CRITICA"], herramienta: "Script propio", protocolo: "SSH" },
  "hydra-sigilosa": { titulo: "Fuerza bruta sigilosa con Hydra", resumen: "Un intento cada 30 s con Hydra, de forma lenta y sostenida.", esperado: ["MEDIA", "CRITICA"], herramienta: "Hydra", protocolo: "SSH" },
  "telnet-fuerza-bruta": { titulo: "Fuerza bruta por Telnet", resumen: "Intentos masivos con Hydra contra el puerto Telnet.", esperado: ["CRITICA"], herramienta: "Hydra", protocolo: "Telnet" },
  "stuffing": { titulo: "Credential stuffing", resumen: "Prueba un gran listado de credenciales filtradas.", esperado: ["CRITICA"], herramienta: "Script propio", protocolo: "SSH" },
  "hydra-stuffing": { titulo: "Credential stuffing con Hydra", resumen: "Prueba credenciales filtradas a alta velocidad con Hydra.", esperado: ["CRITICA"], herramienta: "Hydra", protocolo: "SSH" },
};

const FASES: { nombre: string; ids: string[] }[] = [
  { nombre: "Reconocimiento", ids: ["banner", "nmap-reconocimiento"] },
  { nombre: "Fuerza bruta", ids: ["manual", "rafaga", "persistente", "sigilosa", "hydra-sigilosa", "telnet-fuerza-bruta"] },
  { nombre: "Credential stuffing", ids: ["stuffing", "hydra-stuffing"] },
];

const sinReporteDeResultado = (id?: string) => !!id && (id.startsWith("hydra-") || id === "telnet-fuerza-bruta");

function duracion(e: LabEscenario, count: number, rate: number): string {
  let s: number;
  if (e.params.includes("rate")) s = Math.ceil(count / rate);
  else if (e.intento_s !== null && e.params.includes("count")) s = count * e.intento_s;  // fixed pace
  else return e.duracion;
  if (!Number.isFinite(s)) return e.duracion;
  return s < 90 ? `~${s} s` : `~${(s / 60).toLocaleString("es-AR", { maximumFractionDigits: 1 })} min`;
}

function transcurrido(seg: number): string {
  const s = Math.max(0, Math.floor(seg));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

const nombre = (id?: string) => (id && META[id]?.titulo) || id || "";

export default function Lab() {
  const cat = usePoll(() => api<LabCatalogo>("/lab/scenarios"), [], 0);
  const [activo, setActivo] = useState(false);
  // Poll faster while a run is active (~2 s), slowly otherwise to notice runs started elsewhere.
  const st = usePoll(async () => {
    const s = await api<LabEstado>("/lab/status");
    setActivo(s.estado === "running" || s.estado === "stopping");
    return s;
  }, [activo], activo ? 2000 : 10000);
  const [params, setParams] = useState<Record<string, Valores>>({});
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [abierto, setAbierto] = useState(true);
  const [ahora, setAhora] = useState(() => Date.now() / 1000);

  useEffect(() => {
    if (!activo) return;
    const t = setInterval(() => setAhora(Date.now() / 1000), 1000);
    return () => clearInterval(t);
  }, [activo]);

  const limites = cat.data?.limites;
  const valores = (e: LabEscenario) => params[e.escenario] ?? { count: String(e.count ?? ""), rate: String(e.rate ?? ""), tasks: String(e.tasks ?? "") };
  const setP = (e: LabEscenario, campo: keyof Valores, v: string) =>
    setParams((p) => ({ ...p, [e.escenario]: { ...valores(e), [campo]: v } }));
  const valido = (e: LabEscenario) => {
    if (!e.editable || !limites) return true;
    const v = valores(e);
    const entero = (txt: string, [min, max]: [number, number]) => { const n = Number(txt); return txt !== "" && Number.isInteger(n) && n >= min && n <= max; };
    const r = Number(v.rate);
    return (!e.params.includes("count") || entero(v.count, limites.count))
      && (!e.params.includes("tasks") || entero(v.tasks, limites.tasks))
      && (!e.params.includes("rate") || (v.rate !== "" && r >= limites.rate[0] && r <= limites.rate[1]));
  };

  async function iniciar(e: LabEscenario) {
    setBusy(true); setMsg(null);
    const v = valores(e);
    try {
      const json: Record<string, unknown> = { escenario: e.escenario };
      for (const p of e.params) json[p] = Number(v[p]);
      await api("/lab/runs", { method: "POST", json });
      setAbierto(true);
      await st.reload();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Error");
    } finally { setBusy(false); }
  }

  async function detener() {
    setBusy(true); setMsg(null);
    try {
      await api("/lab/runs/stop", { method: "POST" });
      await st.reload();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Error");
    } finally { setBusy(false); }
  }

  const s = st.data;
  const corriendo = s?.estado === "running" || s?.estado === "stopping";
  const deteniendo = s?.estado === "stopping";
  const hecho = s?.progreso ? s.progreso.ok + s.progreso.fail + s.progreso.err : 0;
  const total = s?.progreso?.total ?? 0;
  const runnerCaido = st.error !== null;
  const fin = s?.fin ?? (corriendo ? ahora : null);
  const tiempo = s?.inicio && fin ? transcurrido(fin - s.inicio) : null;
  const porEscenario = new Map((cat.data?.escenarios ?? []).map((e) => [e.escenario, e]));

  const progreso = s && s.estado !== "idle" && (
    <>
      {corriendo && !(total > 0) && (
        <div className="lab-indet" aria-hidden="true" />
      )}
      {total > 0 && (
        <div className="lab-prog">
          <span>{hecho} / {total} intentos</span>
          <Barra valor={hecho} max={total} />
          {/* Hydra only reports attempts started, not their outcome: don't label them as failures. */}
          {sinReporteDeResultado(s.escenario)
            ? <small className="muted">intentos iniciados {hecho}</small>
            : <small className="muted">ok {s.progreso!.ok} · fallidos {s.progreso!.fail} · errores {s.progreso!.err}</small>}
        </div>
      )}
    </>
  );

  return (
    <>
      <div className="titulo"><h1>Laboratorio de ataques</h1></div>
      <div className="aviso aviso-ok" style={{ display: "grid", gap: 6 }}>
        <span>🛡️ Entorno seguro: los ataques se lanzan dentro de una red de laboratorio aislada y solo contra el honeypot local. Nada sale a Internet.</span>
        <span>ℹ️ ¿No aparece una alerta nueva? El sistema no repite alertas de la misma IP durante 1 hora mientras la anterior esté Nueva o En revisión. Archivala desde Alertas para ver la próxima.</span>
      </div>
      <Estado404 error={cat.error} />
      {runnerCaido && (
        <div className="aviso aviso-error" role="alert">
          {st.error}<br />
          Para habilitarlo, ejecutá: <code>docker compose --profile lab up -d lab-runner</code>
        </div>
      )}
      {msg && <div className="aviso aviso-error" role="alert">{msg}</div>}

      {s && s.estado !== "idle" && (
        <Card className="lab-panel">
          <div className="lab-panel-h">
            <h3>
              {corriendo ? "Ejecución en curso" : "Última ejecución"}: {nombre(s.escenario)}{" "}
              <span className="muted" role="status" aria-live="polite">
                {corriendo && <span className="lab-dot" aria-hidden="true" />}{ESTADO[s.estado]}
              </span>
            </h3>
            <div className="lab-panel-meta">
              {tiempo && <small className="muted">Tiempo: {tiempo}</small>}
              {s.inicio && <small className="muted">Inicio: {new Date(s.inicio * 1000).toLocaleTimeString("es-AR", { hour12: false })}</small>}
              {corriendo && (
                <button className="btn lab-stop" disabled={busy || deteniendo} onClick={() => void detener()}>■ Detener</button>
              )}
              {!corriendo && (
                <button className="btn btn-ghost" aria-expanded={abierto} onClick={() => setAbierto((a) => !a)}>
                  {abierto ? "Ocultar" : "Mostrar"}
                </button>
              )}
            </div>
          </div>
          {(corriendo || abierto) && (
            <div className="lab-panel-body">
              {progreso}
              <pre className="tty" aria-label="Salida del comando">{s.salida.length ? s.salida.slice(-30).join("\n") : "(sin salida todavía)"}</pre>
            </div>
          )}
        </Card>
      )}

      {FASES.map((f) => {
        const lista = f.ids.map((id) => porEscenario.get(id as LabEscenario["escenario"])).filter((e): e is LabEscenario => !!e);
        if (!lista.length) return null;
        return (
          <section key={f.nombre} aria-label={f.nombre}>
            <h2 className="lab-fase">{f.nombre}</h2>
            <div className="lab-grid">
              {lista.map((e) => {
                const m = META[e.escenario];
                const v = valores(e);
                const mio = corriendo && s?.escenario === e.escenario;
                return (
                  <article key={e.escenario} className={`card lab-card${mio ? " activa" : ""}`}>
                    <div className="lab-card-h">
                      <h4>{m?.titulo ?? e.escenario}</h4>
                      <div className="lab-badges" aria-label="Resultado esperado">
                        {(m?.esperado ?? []).map((c, i) => (
                          <span key={c}>{i > 0 && <span className="muted" aria-hidden="true">→ </span>}<Badge clase={c} /></span>
                        ))}
                      </div>
                    </div>
                    <p className="lab-desc">{m?.resumen ?? e.descripcion}</p>
                    <div className="lab-chips">
                      {m && <span className="lab-chip">{m.herramienta}</span>}
                      {m && <span className="lab-chip">{m.protocolo}</span>}
                      <span className="lab-chip">{duracion(e, Number(v.count), Number(v.rate))}</span>
                    </div>
                    <code className="lab-cmd" title={e.comando}>{e.comando}</code>
                    <details className="lab-det">
                      <summary>Detalles</summary>
                      <p>{e.descripcion}</p>
                    </details>
                    {e.editable && (
                      <div className="lab-params">
                        {e.params.includes("count") && (
                          <label>Intentos
                            <input type="number" min={limites?.count[0]} max={limites?.count[1]} step={1} value={v.count}
                              disabled={corriendo} onChange={(ev) => setP(e, "count", ev.target.value)} />
                          </label>
                        )}
                        {e.params.includes("rate") && (
                          <label>Por segundo
                            <input type="number" min={limites?.rate[0]} max={limites?.rate[1]} step={0.1} value={v.rate}
                              disabled={corriendo} onChange={(ev) => setP(e, "rate", ev.target.value)} />
                          </label>
                        )}
                        {e.params.includes("tasks") && (
                          <label>Tareas en paralelo
                            <input type="number" min={limites?.tasks[0]} max={limites?.tasks[1]} step={1} value={v.tasks}
                              disabled={corriendo} onChange={(ev) => setP(e, "tasks", ev.target.value)} />
                          </label>
                        )}
                      </div>
                    )}
                    <div className="lab-foot">
                      {mio && (total > 0 ? <Barra valor={hecho} max={total} /> : <div className="lab-indet" aria-hidden="true" />)}
                      {mio ? (
                        <button className="btn lab-stop" disabled={busy || deteniendo} onClick={() => void detener()}>
                          {deteniendo ? "Deteniendo…" : "■ Detener"}
                        </button>
                      ) : (
                        <button className="btn" disabled={busy || corriendo || runnerCaido || !valido(e)} onClick={() => void iniciar(e)}
                          aria-label={`Iniciar ${m?.titulo ?? e.escenario}`}>▶ Iniciar</button>
                      )}
                      {corriendo && !mio && <small className="muted">Hay un ataque en curso</small>}
                    </div>
                  </article>
                );
              })}
            </div>
          </section>
        );
      })}
    </>
  );
}
