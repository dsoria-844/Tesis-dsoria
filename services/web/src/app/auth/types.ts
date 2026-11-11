export type Rol = "RESPONSABLE_SEGURIDAD" | "AUDITOR" | "ADMIN_INFRA";

export interface Me {
  id: string;
  correo: string;
  rol: Rol;
}
