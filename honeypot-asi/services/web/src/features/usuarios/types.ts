import type { Rol } from "../../app/auth/types";

export interface Usuario {
  id: string;
  correo: string;
  rol: Rol;
  estado: string;
  bloqueado_hasta: string | null;
  fecha_creacion: string;
}
