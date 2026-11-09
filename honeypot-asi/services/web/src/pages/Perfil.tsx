import { useRef, useState, type FormEvent } from "react";
import { api, type Acceso, type Perfil as PerfilT, type ReinicioOut, type Rol } from "../api";
import { ROL, useAuth } from "../App";
import { Card, Estado404, fecha, num, usePoll } from "../components/ui";
import { limpiarVista, restablecerVista, useDesde } from "../vista";

const DESCRIPCION: Record<Rol, string> = {
  RESPONSABLE_SEGURIDAD: "Consulta el panel, las sesiones, las alertas y las credenciales capturadas.",
  AUDITOR: "Consulta la telemetría y revisa las alertas: cambia su estado y registra observaciones.",
  ADMIN_INFRA: "Administra usuarios y ejecuta el laboratorio de ataques. No accede a la telemetría ni a las alertas.",
};
const EVENTO: Record<string, [string, string]> = {
  LOGIN_OK: ["Inicio de sesión", "Correcto"],
  LOGIN_FAIL: ["Inicio de sesión", "Fallido"],
  LOCKOUT: ["Bloqueo de cuenta", "Bloqueada"],
};
const ELIMINADO: Record<string, string> = {
  sesiones: "sesiones", intentos_login: "intentos de login", comandos_ejecutados: "comandos",
  evaluaciones_asi: "evaluaciones ASI", alertas_seguridad: "alertas", alertas_historial: "historial de alertas",
};

function ReinicioLab() {
  const ref = useRef<HTMLDialogElement>(null);
  const [texto, setTexto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [res, setRes] = useState<ReinicioOut | null>(null);

  const abrir = () => { setTexto(""); setError(null); setRes(null); ref.current?.showModal(); };
  const cerrar = () => ref.current?.close();

  const confirmar = async (e: FormEvent) => {
    e.preventDefault();
    if (texto !== "REINICIAR") return;
    setEnviando(true);
    setError(null);
    try {
      setRes(await api<ReinicioOut>("/lab/reiniciar", { method: "POST", json: { confirmacion: texto } }));
      cerrar();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo reiniciar el laboratorio");
    } finally {
      setEnviando(false);
    }
  };

  return (
    <Card titulo="Zona de peligro · Reiniciar laboratorio" className="card-peligro">
      <p>
        Borra <b>definitivamente</b> la telemetría del laboratorio para empezar una demostración limpia: sesiones,
        intentos de login, comandos, evaluaciones ASI, alertas y el historial de alertas.
      </p>
      <p className="muted">
        Se conservan: los usuarios, el registro de accesos (auditoría), los sensores y el avance de lectura del log,
        por lo que no se vuelve a importar lo ya procesado. La acción queda registrada en el registro de accesos.
        Solo para uso en laboratorio.
      </p>
      {res && (
        <div className="aviso aviso-ok" role="status">
          Laboratorio reiniciado. Eliminados:{" "}
          {Object.entries(res.eliminados).map(([k, v]) => `${num(v)} ${ELIMINADO[k] ?? k}`).join(" · ")}.
        </div>
      )}
      <div className="acciones">
        <button type="button" className="btn btn-peligro" onClick={abrir}>Confirmar</button>
      </div>
      <dialog ref={ref} className="modal" aria-labelledby="reinicio-titulo">
        <form onSubmit={confirmar} className="form" style={{ marginTop: 0 }}>
          <h3 id="reinicio-titulo">¿Reiniciar el laboratorio?</h3>
          <p className="muted" style={{ margin: 0 }}>
            Esta acción no se puede deshacer. Para confirmar, escribí <code>REINICIAR</code>.
          </p>
          <label>
            Confirmación
            <input value={texto} onChange={(e) => setTexto(e.target.value)} autoComplete="off" spellCheck={false}
              aria-describedby="reinicio-ayuda" />
          </label>
          <small id="reinicio-ayuda" className="muted">Se distingue entre mayúsculas y minúsculas.</small>
          {error && <div className="aviso aviso-error" role="alert">{error}</div>}
          <div className="acciones" style={{ justifyContent: "flex-end" }}>
            <button type="button" className="btn btn-ghost" onClick={cerrar}>Cancelar</button>
            <button type="submit" className="btn btn-peligro" disabled={texto !== "REINICIAR" || enviando}>
              {enviando ? "Reiniciando…" : "Borrar telemetría"}
            </button>
          </div>
        </form>
      </dialog>
    </Card>
  );
}

export default function Perfil() {
  const { me, logout } = useAuth();
  const perfil = usePoll(() => api<PerfilT>("/me/perfil"), [], 0);
  const accesos = usePoll(() => api<Acceso[]>("/me/accesos"), [], 0);
  const desde = useDesde(me.id);
  const p = perfil.data;

  return (
    <>
      <div className="titulo">
        <h1>Mi perfil</h1>
        <button type="button" className="btn btn-ghost" onClick={logout}>Cerrar sesión</button>
      </div>

      <Card titulo="Datos de la cuenta">
        <Estado404 error={perfil.error} />
        {p && (
          <dl className="dl">
            <dt>Correo</dt><dd>{p.correo}</dd>
            <dt>Rol</dt><dd><b>{ROL[p.rol]}</b><br /><span className="muted">{DESCRIPCION[p.rol]}</span></dd>
            <dt>Estado de la cuenta</dt><dd>{p.estado === "ACTIVO" ? "Activa" : "Inactiva"}</dd>
            <dt>Cuenta creada</dt><dd>{fecha(p.fecha_creacion)}</dd>
          </dl>
        )}
      </Card>

      <Card titulo="Mis últimos accesos">
        <Estado404 error={accesos.error} />
        {accesos.data && accesos.data.length === 0 && <p className="muted">Sin accesos registrados.</p>}
        {accesos.data && accesos.data.length > 0 && (
          <table>
            <thead><tr><th>Fecha</th><th>IP</th><th>Evento</th><th>Resultado</th></tr></thead>
            <tbody>
              {accesos.data.map((a, i) => {
                const [ev, res] = EVENTO[a.evento] ?? [a.evento, "—"];
                return (
                  <tr key={`${a.fecha}-${i}`}>
                    <td>{fecha(a.fecha)}</td><td>{a.ip_cliente ? <code>{a.ip_cliente}</code> : "—"}</td>
                    <td>{ev}</td>
                    <td>{res === "Correcto" ? res : <span className="estado estado-nueva">{res}</span>}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Card>

      <Card titulo="Vista de actividad reciente">
        <p>
          Oculta, solo para vos y en este navegador, la actividad anterior a este momento en la tarjeta
          «Actividad reciente» y en la página de actividad por IP. <b>No borra ningún dato</b>: el resto de los
          usuarios y las demás secciones no cambian.
        </p>
        <p className="muted" role="status">
          {desde ? `Vista limpiada el ${fecha(desde)}.` : "La vista no está limpiada: se muestra toda la actividad."}
        </p>
        <div className="acciones">
          <button type="button" className="btn btn-ghost" onClick={() => limpiarVista(me.id)}>
            Limpiar mi vista de actividad reciente
          </button>
          <button type="button" className="btn btn-ghost" disabled={!desde} onClick={() => restablecerVista(me.id)}>
            Restablecer vista
          </button>
        </div>
      </Card>

      {me.rol === "ADMIN_INFRA" && <ReinicioLab />}
    </>
  );
}
