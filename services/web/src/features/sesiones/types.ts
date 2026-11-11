import type { Sesion } from "../../shared/api/types";

export interface SesionDetalle extends Sesion {
  sensor: string;
  intentos: {
    timestamp_evento: string;
    usuario_ensayado: string;
    password_ensayado: string | null;
    autenticado: boolean;
  }[];
  comandos: {
    timestamp_evento: string;
    tipo_evento: string;
    comando_tipeado: string;
    url_descarga: string | null;
    hash_descarga_sha256: string | null;
  }[];
}
