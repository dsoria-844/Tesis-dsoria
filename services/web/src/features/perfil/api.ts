import { api } from "../../shared/api/client";
import type { Acceso, Perfil, ReinicioOut } from "./types";

export const obtenerPerfil = () => api<Perfil>("/me/perfil");
export const obtenerAccesos = () => api<Acceso[]>("/me/accesos");
export const reiniciarLaboratorio = (confirmacion: string) =>
  api<ReinicioOut>("/lab/reiniciar", { method: "POST", json: { confirmacion } });
