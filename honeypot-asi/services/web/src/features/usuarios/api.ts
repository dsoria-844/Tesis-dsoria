import { api } from "../../shared/api/client";
import type { Rol } from "../../app/auth/types";
import type { Usuario } from "./types";

export const listarUsuarios = () => api<Usuario[]>("/users");
export const crearUsuario = (correo: string, password: string, rol: Rol) =>
  api("/users", { method: "POST", json: { correo, password, rol } });
export const cambiarEstadoUsuario = (id: string, estado: "ACTIVO" | "INACTIVO") =>
  api(`/users/${id}`, { method: "PATCH", json: { estado } });
