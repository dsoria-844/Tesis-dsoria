import { api } from "../../shared/api/client";
import type { Pagina, Sesion } from "../../shared/api/types";
import type { SesionDetalle } from "./types";

export const listarSesiones = (qs: URLSearchParams) => api<Pagina<Sesion>>(`/sessions?${qs}`);
export const obtenerSesion = (id: string) => api<SesionDetalle>(`/sessions/${id}`);
