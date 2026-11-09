import { useState } from "react";
import { Link } from "react-router-dom";
import { api, type ActividadVivo } from "../api";
import { Card, Estado404, fecha, num, usePoll } from "../components/ui";
import TablaActividad from "../components/TablaActividad";
import { useAuth } from "../App";
import { conDesde, restablecerVista, useDesde } from "../vista";

const PAGE = 50;

async function cargar(paginas: number, desde: string | null): Promise<ActividadVivo> {
  // Refresh every loaded page (limit is capped at 200 server-side); drop IPs repeated when pages shift.
  const rs = await Promise.all(
    Array.from({ length: paginas }, (_, i) => api<ActividadVivo>(conDesde(`/metrics/live?todo=true&limit=${PAGE}&offset=${i * PAGE}`, desde))),
  );
  const vistas = new Set<string>();
  const items = rs.flatMap((r) => r.items).filter((a) => !vistas.has(a.ip_origen) && vistas.add(a.ip_origen));
  return { ...rs[0], items };
}

export default function Actividad() {
  const [paginas, setPaginas] = useState(1);
  const { me } = useAuth();
  const desde = useDesde(me.id);
  const v = usePoll(() => cargar(paginas, desde), [paginas, desde], 5000);
  const d = v.data;
  return (
    <>
      <div className="titulo">
        <h1>Todas las IPs de origen</h1>
        <Link to="/" className="btn btn-ghost">← Volver al panel</Link>
      </div>
      <Card
        titulo="Actividad histórica por IP"
        extra={<span className="en-vivo"><i className="punto-vivo" aria-hidden="true" />En vivo</span>}
      >
        <Estado404 error={v.error} />
        {desde && (
          <p className="muted">
            Vista limpiada el {fecha(desde)} ·{" "}
            <button type="button" className="link-btn" onClick={() => restablecerVista(me.id)}>Restablecer</button>
          </p>
        )}
        {d && d.items.length === 0 && (
          <p className="muted">{desde ? "No hay actividad nueva desde que limpiaste la vista." : "Todavía no se recibieron ataques."}</p>
        )}
        {d && d.items.length > 0 && (
          <>
            <p className="muted">
              {num(d.totales.ips)} IP · {num(d.totales.sesiones)} sesiones · {num(d.totales.intentos_login)} intentos de login · {num(d.totales.comandos)} comandos
            </p>
            <TablaActividad items={d.items} ahora={d.ahora} />
            <p className="muted">Mostrando {num(d.items.length)} de {num(d.total_ips)} IP.</p>
            {d.items.length < d.total_ips && (
              <button className="btn btn-ghost" onClick={() => setPaginas((p) => p + 1)}>Cargar más</button>
            )}
          </>
        )}
      </Card>
    </>
  );
}
