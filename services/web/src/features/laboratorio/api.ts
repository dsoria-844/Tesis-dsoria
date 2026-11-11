import { api } from "../../shared/api/client";
import type { LabCatalogo, LabEstado } from "./types";

export const obtenerCatalogo = () => api<LabCatalogo>("/lab/scenarios");
export const obtenerEstado = () => api<LabEstado>("/lab/status");
export const iniciarEscenario = (json: Record<string, unknown>) => api("/lab/runs", { method: "POST", json });
export const detenerEscenario = () => api("/lab/runs/stop", { method: "POST" });
