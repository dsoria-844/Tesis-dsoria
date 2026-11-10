import type { Rol } from "../../app/auth/types";

export interface Perfil {
  id: string;
  correo: string;
  rol: Rol;
  estado: string;
  fecha_creacion: string;
}

export interface Acceso {
  fecha: string;
  ip_cliente: string | null;
  evento: string;
  detalle: string | null;
}

export interface ReinicioOut {
  eliminados: Record<string, number>;
}
