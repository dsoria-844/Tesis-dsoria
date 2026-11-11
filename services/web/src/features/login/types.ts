import type { Rol } from "../../app/auth/types";

export interface TokenOut {
  access_token: string;
  rol: Rol;
  correo: string;
}
