import { api } from "../../shared/api/client";
import type { ActividadVivo } from "../../shared/api/types";
import { conDesde } from "../../shared/lib/vista";

export const obtenerActividadPagina = (limit: number, offset: number, desde: string | null) =>
  api<ActividadVivo>(conDesde(`/metrics/live?todo=true&limit=${limit}&offset=${offset}`, desde));
