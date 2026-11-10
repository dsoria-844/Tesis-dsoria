import { Link, useNavigate } from "react-router-dom";
import type { ActividadIp } from "../api/types";
import { dec, hace, num } from "../lib/format";
import { Badge } from "./Badge";

/** Per-IP activity table shared by the dashboard card and the full listing. `ahora` is the server clock. */
export default function TablaActividad({ items, ahora }: { items: ActividadIp[]; ahora: string }) {
  const nav = useNavigate();
  const edad = (iso: string) => (new Date(ahora).getTime() - new Date(iso).getTime()) / 1000;
  return (
    <div className="tabla-wrap">
      <table className="clic" style={{ minWidth: 640 }}>
        <thead>
          <tr>
            <th>IP de origen</th>
            <th>Protocolo</th>
            <th>Sesiones</th>
            <th>Intentos</th>
            <th>Último evento</th>
            <th>Severidad</th>
            <th>Alerta</th>
          </tr>
        </thead>
        <tbody>
          {items.map((a) => {
            const seg = edad(a.ultimo_evento);
            return (
              <tr
                key={a.ip_origen}
                className={seg < 10 ? "fila-viva" : ""}
                onClick={() => nav(`/ip/${encodeURIComponent(a.ip_origen)}`)}
              >
                <td>
                  <Link
                    to={`/ip/${encodeURIComponent(a.ip_origen)}`}
                    onClick={(e) => e.stopPropagation()}
                    title="Ver detalle de la IP"
                  >
                    <code>{a.ip_origen}</code>
                  </Link>
                </td>
                <td className="muted">{a.protocolos.join(" · ")}</td>
                <td className="num">{num(a.sesiones)}</td>
                <td className="num">{num(a.intentos_login)}</td>
                <td className="muted">{hace(seg)}</td>
                <td>
                  {a.puntaje_asi == null || a.clasificacion == null ? (
                    <span className="muted">—</span>
                  ) : (
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                      <Badge clase={a.clasificacion} />
                      <b className="num">{dec(a.puntaje_asi)}</b>
                    </span>
                  )}
                </td>
                <td>
                  {a.alerta_abierta ? (
                    <span className="tag estado-nueva">Alerta</span>
                  ) : (
                    <span className="muted">—</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
