import { Link, useNavigate } from "react-router-dom";
import type { ActividadIp } from "../api";
import { Badge, Barra, COLOR, num } from "./ui";

export function hace(seg: number): string {
  if (seg < 60) return `hace ${Math.max(0, Math.round(seg))} s`;
  return `hace ${Math.floor(seg / 60)} min ${Math.round(seg % 60)} s`;
}

/** Per-IP activity table shared by the dashboard card and the full listing. `ahora` is the server clock. */
export default function TablaActividad({ items, ahora }: { items: ActividadIp[]; ahora: string }) {
  const nav = useNavigate();
  const edad = (iso: string) => (new Date(ahora).getTime() - new Date(iso).getTime()) / 1000;
  return (
    <table className="clic">
      <thead><tr><th>IP origen</th><th>Protocolo</th><th>Sesiones</th><th>Intentos</th><th>Último evento</th><th>ASI</th><th>Alerta</th></tr></thead>
      <tbody>
        {items.map((a) => {
          const seg = edad(a.ultimo_evento);
          return (
            <tr key={a.ip_origen} className={seg < 10 ? "fila-viva" : ""} onClick={() => nav(`/ip/${encodeURIComponent(a.ip_origen)}`)}>
              <td>
                <Link to={`/ip/${encodeURIComponent(a.ip_origen)}`} onClick={(e) => e.stopPropagation()} title="Ver detalle de la IP">
                  <code>{a.ip_origen}</code>
                </Link>
              </td>
              <td>{a.protocolos.join(", ")}</td>
              <td>{num(a.sesiones)}</td>
              <td>{num(a.intentos_login)}</td>
              <td>{hace(seg)}</td>
              <td>
                {a.puntaje_asi == null || a.clasificacion == null ? <span className="muted">—</span> : (
                  <div className="fila-asi" style={{ gridTemplateColumns: "80px 48px auto", padding: 0 }}>
                    <Barra valor={a.puntaje_asi} color={COLOR[a.clasificacion]} />
                    <strong>{a.puntaje_asi.toFixed(3)}</strong>
                    <span style={{ justifySelf: "start" }}><Badge clase={a.clasificacion} /></span>
                  </div>
                )}
              </td>
              <td>{a.alerta_abierta ? <span className="estado estado-nueva">Alerta</span> : "—"}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
