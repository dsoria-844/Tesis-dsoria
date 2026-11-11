import { api } from "../../shared/api/client";
import type { Pagina, Sesion } from "../../shared/api/types";
import type { AlertasIp, AsiIp, CredencialesIp, ResumenIp } from "./types";

export const obtenerCredencialesIp = (ip: string) =>
  api<CredencialesIp>(`/ips/${encodeURIComponent(ip)}/credenciales?limit=10`);
export const listarSesionesIp = (ip: string, limite: number, offset: number) =>
  api<Pagina<Sesion>>(`/ips/${encodeURIComponent(ip)}/sesiones?limit=${limite}&offset=${offset}`);
export const obtenerAlertasIp = (ip: string) => api<AlertasIp>(`/ips/${encodeURIComponent(ip)}/alertas`);
export const obtenerResumenIp = (ip: string) => api<ResumenIp>(`/ips/${encodeURIComponent(ip)}/resumen`);
export const obtenerAsiIp = (ip: string) => api<AsiIp>(`/ips/${encodeURIComponent(ip)}/asi`);
