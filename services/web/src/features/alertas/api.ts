import { api } from "../../shared/api/client";
import type { Alerta, AlertaDetalle, Credenciales, Estado, Pagina } from "../../shared/api/types";

export const listarAlertas = (estado: Estado | "") =>
  api<Pagina<Alerta>>(`/alerts?limit=50${estado ? `&estado=${estado}` : ""}`);
export const contarAlertas = (estado: Estado) => api<Pagina<Alerta>>(`/alerts?limit=1&estado=${estado}`);
export const obtenerAlerta = (id: number) => api<AlertaDetalle>(`/alerts/${id}`);
export const actualizarAlerta = (id: number, estado: Estado, obs: string) =>
  api(`/alerts/${id}`, { method: "PATCH", json: { estado_alerta: estado, observaciones_auditor: obs } });
export const obtenerCredencialesTop = () => api<Credenciales>("/credentials/top?horas=24&limit=8");
