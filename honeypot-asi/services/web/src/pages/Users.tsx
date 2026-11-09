import { useState, type FormEvent } from "react";
import { api, type Rol, type Usuario } from "../api";
import { Card, Estado404, fecha, usePoll } from "../components/ui";

const ROLES: Rol[] = ["AUDITOR", "RESPONSABLE_SEGURIDAD", "ADMIN_INFRA"];

export default function Users() {
  const lista = usePoll(() => api<Usuario[]>("/users"), [], 0);
  const [correo, setCorreo] = useState("");
  const [password, setPassword] = useState("");
  const [rol, setRol] = useState<Rol>("AUDITOR");
  const [msg, setMsg] = useState<{ ok: boolean; texto: string } | null>(null);

  async function crear(e: FormEvent) {
    e.preventDefault();
    try {
      await api("/users", { method: "POST", json: { correo, password, rol } });
      setMsg({ ok: true, texto: `Usuario ${correo} creado.` });
      setCorreo(""); setPassword("");
      await lista.reload();
    } catch (err) {
      setMsg({ ok: false, texto: err instanceof Error ? err.message : "Error" });
    }
  }

  async function cambiar(u: Usuario, estado: "ACTIVO" | "INACTIVO") {
    try {
      await api(`/users/${u.id}`, { method: "PATCH", json: { estado } });
      await lista.reload();
    } catch (err) {
      setMsg({ ok: false, texto: err instanceof Error ? err.message : "Error" });
    }
  }

  return (
    <>
      <div className="page-head"><div><h1>Usuarios</h1><p>Creá, desactivá y reactivá las cuentas personales del panel.</p></div></div>
      <div className="grid2 wide-left">
        <Card titulo="Cuentas del panel">
          <Estado404 error={lista.error} />
          <div className="tabla-wrap"><table style={{ minWidth: 560 }}>
            <thead><tr><th>Correo</th><th>Perfil</th><th>Estado</th><th>Alta</th><th /></tr></thead>
            <tbody>
              {lista.data?.map((u) => (
                <tr key={u.id}>
                  <td>{u.correo}</td><td>{u.rol.replace(/_/g, " ")}</td>
                  <td>{u.estado === "ACTIVO" ? <span className="tag" style={{ background: "var(--baja-bg)", color: "var(--baja-fg)" }}>Activo</span> : <span className="tag">Inactivo</span>}{u.bloqueado_hasta && new Date(u.bloqueado_hasta) > new Date() ? <> <span className="tag estado-nueva">Bloqueado</span></> : ""}</td>
                  <td className="muted">{fecha(u.fecha_creacion)}</td>
                  <td>
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => void cambiar(u, u.estado === "ACTIVO" ? "INACTIVO" : "ACTIVO")}>
                      {u.estado === "ACTIVO" ? "Dar de baja" : "Reactivar"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table></div>
        </Card>
        <Card titulo="Alta de usuario">
          <form className="form" onSubmit={crear}>
            <label>Correo<input type="email" value={correo} onChange={(e) => setCorreo(e.target.value)} required /></label>
            <label>Contraseña (mín. 12 caracteres)<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={12} /></label>
            <label>Perfil
              <select value={rol} onChange={(e) => setRol(e.target.value as Rol)}>
                {ROLES.map((r) => <option key={r} value={r}>{r.replace(/_/g, " ")}</option>)}
              </select>
            </label>
            <button className="btn">Crear usuario</button>
            {msg && <div className={`aviso ${msg.ok ? "aviso-ok" : "aviso-error"}`} role="status">{msg.texto}</div>}
          </form>
        </Card>
      </div>
    </>
  );
}
