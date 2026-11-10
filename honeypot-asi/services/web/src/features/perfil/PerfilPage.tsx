import { ROL } from "../../app/auth/roles";
import { useAuth } from "../../app/auth/useAuth";
import type { Rol } from "../../app/auth/types";
import { usePoll } from "../../shared/hooks/usePoll";
import { fecha } from "../../shared/lib/format";
import { limpiarVista, restablecerVista, useDesde } from "../../shared/lib/vista";
import { Card } from "../../shared/ui/Card";
import { Estado404 } from "../../shared/ui/Estado404";
import { obtenerAccesos, obtenerPerfil } from "./api";
import ReinicioLab from "./ReinicioLab";

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
export default function Perfil() {
  const { me, logout } = useAuth();
  const perfil = usePoll(() => obtenerPerfil(), [], 0);
  const accesos = usePoll(() => obtenerAccesos(), [], 0);
  const desde = useDesde(me.id);
  const p = perfil.data;

  return (
    <div className="stack narrow-col" style={{ gap: 20 }}>
      <div className="perfil-head">
        <span className="avatar lg" aria-hidden="true">
          {me.correo
            .replace(/[^a-zA-Z0-9]/g, "")
            .slice(0, 2)
            .toUpperCase()}
        </span>
        <div>
          <h1>{me.correo}</h1>
          <p className="muted">
            {ROL[me.rol]}
            {p &&
              ` · cuenta ${p.estado === "ACTIVO" ? "activa" : "inactiva"} desde el ${new Date(p.fecha_creacion).toLocaleDateString("es-AR")}`}
          </p>
        </div>
        <button type="button" className="btn btn-ghost" onClick={logout}>
          Cerrar sesión
        </button>
      </div>
      <Estado404 error={perfil.error} />

      <Card titulo="Qué puede hacer este rol">
        <p className="muted" style={{ color: "var(--ink-2)" }}>
          {DESCRIPCION[me.rol]}
        </p>
      </Card>

      <Card titulo="Últimos accesos">
        <Estado404 error={accesos.error} />
        {accesos.data && accesos.data.length === 0 && <p className="muted">Sin accesos registrados.</p>}
        {accesos.data && accesos.data.length > 0 && (
          <div className="tabla-wrap">
            <table style={{ minWidth: 480 }}>
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th>IP</th>
                  <th>Evento</th>
                  <th>Resultado</th>
                </tr>
              </thead>
              <tbody>
                {accesos.data.map((a, i) => {
                  const [ev, res] = EVENTO[a.evento] ?? [a.evento, "—"];
                  return (
                    <tr key={`${a.fecha}-${i}`}>
                      <td>{fecha(a.fecha)}</td>
                      <td>{a.ip_cliente ? <code>{a.ip_cliente}</code> : "—"}</td>
                      <td>{ev}</td>
                      <td>
                        {res === "Correcto" ? (
                          <span style={{ color: "var(--baja-fg)", fontWeight: 500 }}>{res}</span>
                        ) : (
                          <span className="tag estado-nueva">{res}</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <section className="card accion" aria-labelledby="vista-h">
        <div>
          <h2 id="vista-h">Limpiar mi vista</h2>
          <p>
            Oculta, solo para vos y en este navegador, la actividad anterior a este momento en «Actividad reciente» y en
            la página de actividad por IP. <b>No borra ningún dato</b>.
          </p>
          <p role="status">{desde ? `Vista limpiada el ${fecha(desde)}.` : "Estás viendo toda la actividad."}</p>
        </div>
        <div className="acciones" style={{ marginTop: 0 }}>
          <button type="button" className="btn btn-ghost" onClick={() => limpiarVista(me.id)}>
            Limpiar vista
          </button>
          <button type="button" className="btn btn-ghost" disabled={!desde} onClick={() => restablecerVista(me.id)}>
            Restablecer vista
          </button>
        </div>
      </section>

      {me.rol === "ADMIN_INFRA" && <ReinicioLab />}
    </div>
  );
}
