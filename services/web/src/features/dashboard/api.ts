import { api } from "../../shared/api/client";
import type { ActividadVivo } from "../../shared/api/types";
import { conDesde } from "../../shared/lib/vista";
import type { Metricas, SerieOut, VistaSerie } from "./types";

export const obtenerActividadEnVivo = (desde: string | null) =>
  api<ActividadVivo>(conDesde("/metrics/live?todo=true&limit=3", desde));
export const obtenerMetricas = (horas: number) => api<Metricas>(`/metrics?horas=${horas}`);
export const obtenerSerie = (vista: VistaSerie, tz: string) =>
  api<SerieOut>(`/metrics/serie?vista=${vista}&tz=${encodeURIComponent(tz)}`);
