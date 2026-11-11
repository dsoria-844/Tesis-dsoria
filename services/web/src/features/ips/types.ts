import type { AlertaDetalle, Credenciales } from "../../shared/api/types";

export interface ResumenIp {
  ip_origen: string;
  protocolos: string[];
  primer_evento: string | null;
  ultimo_evento: string | null;
  sesiones: number;
  intentos_login: number;
  intentos_exitosos: number;
  comandos: number;
  alerta_abierta: boolean;
}

export interface AsiIp {
  ip_origen: string;
  ultima: null | {
    fecha_calculo: string;
    ventana_segundos: number;
    n_intentos: number;
    k_pares_distintos: number;
    componentes: {
      clave: "frecuencia" | "volumen" | "diversidad" | "persistencia";
      valor: number;
      peso: number;
      aporte: number;
    }[];
    puntaje_asi: number;
    clasificacion: string;
  };
  serie: { fecha_calculo: string; puntaje_asi: number; clasificacion: string; ventana_segundos: number }[];
}

export interface CredencialesIp extends Credenciales {
  ip_origen: string;
}

export interface AlertasIp {
  ip_origen: string;
  total: number;
  items: AlertaDetalle[];
}
