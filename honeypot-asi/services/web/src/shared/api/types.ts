export type Estado = "NUEVA" | "EN_REVISION" | "ARCHIVADA";

export interface Pagina<T> {
  total: number;
  limit: number;
  offset: number;
  items: T[];
}

export interface Conteo {
  valor: string;
  intentos: number;
  porcentaje: number;
}

export interface Credenciales {
  total_intentos: number;
  usuarios: Conteo[];
  passwords: Conteo[];
  pares: Conteo[];
}

export interface Sesion {
  id: string;
  session_cowrie_id: string;
  ip_origen: string;
  puerto_origen: number | null;
  protocolo: "SSH" | "TELNET";
  fecha_inicio: string;
  fecha_fin: string | null;
  duracion_segundos: number | null;
  n_intentos: number;
  n_comandos: number;
  obtuvo_acceso: boolean;
}

export interface Alerta {
  id: number;
  ip_origen: string;
  fecha_disparo: string;
  nivel_criticidad: string;
  puntaje_asi: number;
  estado_alerta: Estado;
  observaciones_auditor: string | null;
  desglose: {
    frecuencia: number;
    volumen: number;
    diversidad: number;
    persistencia: number;
    n_intentos: number;
    k_pares_distintos: number;
    ventana_segundos: number;
  };
}

export interface AlertaDetalle extends Alerta {
  historial: {
    fecha: string;
    auditor: string;
    estado_anterior: string | null;
    estado_nuevo: string | null;
    observaciones_nueva: string | null;
  }[];
}

export interface ActividadIp {
  ip_origen: string;
  protocolos: string[];
  sesiones: number;
  intentos_login: number;
  intentos_exitosos: number;
  comandos: number;
  ultimo_evento: string;
  puntaje_asi: number | null;
  clasificacion: string | null;
  fecha_calculo: string | null;
  alerta_abierta: boolean;
}

export interface ActividadVivo {
  minutos: number | null;
  ahora: string;
  totales: { ips: number; sesiones: number; intentos_login: number; comandos: number };
  total_ips: number;
  limit: number;
  offset: number;
  items: ActividadIp[];
}
