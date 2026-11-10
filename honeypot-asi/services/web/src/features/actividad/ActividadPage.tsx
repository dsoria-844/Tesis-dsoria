import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../app/auth/useAuth";
import type { ActividadVivo } from "../../shared/api/types";
import { usePoll } from "../../shared/hooks/usePoll";
import { fecha, num } from "../../shared/lib/format";
import { restablecerVista, useDesde } from "../../shared/lib/vista";
import { Card } from "../../shared/ui/Card";
import { Estado404 } from "../../shared/ui/Estado404";
import TablaActividad from "../../shared/ui/TablaActividad";
import { obtenerActividadPagina } from "./api";

const PAGE = 50;

async function cargar(paginas: number, desde: string | null): Promise<ActividadVivo> {
  // Refresh every loaded page (limit is capped at 200 server-side); drop IPs repeated when pages shift.
  const rs = await Promise.all(
    Array.from({ length: paginas }, (_, i) => obtenerActividadPagina(PAGE, i * PAGE, desde)),
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
  // "En vivo" only while the most recent event is fresh (< 5 min), as on the dashboard card.
  const ultimo = d?.items[0]?.ultimo_evento;
  const activo = !!(d && ultimo && new Date(d.ahora).getTime() - new Date(ultimo).getTime() < 5 * 60 * 1000);
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Actividad</h1>
          <p>Todas las IPs de origen registradas por el honeypot, de la más reciente a la más antigua.</p>
        </div>
        <Link to="/" className="btn btn-ghost">
          ← Volver al resumen
        </Link>
      </div>
      <Card
        titulo="Actividad histórica por IP"
        extra={
          activo ? (
            <span className="en-vivo">
              <i className="punto-vivo" aria-hidden="true" />
              En vivo
            </span>
          ) : (
            <span className="muted" style={{ fontSize: 12 }}>
              Sin ataques en curso
            </span>
          )
        }
      >
        <Estado404 error={v.error} />
        {desde && (
          <p className="muted">
            Vista limpiada el {fecha(desde)} ·{" "}
            <button type="button" className="link-btn" onClick={() => restablecerVista(me.id)}>
              Restablecer
            </button>
          </p>
        )}
        {d && d.items.length === 0 && (
          <p className="muted">
            {desde ? "No hay actividad nueva desde que limpiaste la vista." : "Todavía no se registraron ataques."}
          </p>
        )}
        {d && d.items.length > 0 && (
          <>
            <p className="muted">
              {num(d.totales.ips)} IP · {num(d.totales.sesiones)} sesiones · {num(d.totales.intentos_login)} intentos de
              login · {num(d.totales.comandos)} comandos
            </p>
            <TablaActividad items={d.items} ahora={d.ahora} />
            <p className="muted">
              Mostrando {num(d.items.length)} de {num(d.total_ips)} IP.
            </p>
            {d.items.length < d.total_ips && (
              <button type="button" className="btn btn-ghost" onClick={() => setPaginas((p) => p + 1)}>
                Cargar más
              </button>
            )}
          </>
        )}
      </Card>
    </>
  );
}
