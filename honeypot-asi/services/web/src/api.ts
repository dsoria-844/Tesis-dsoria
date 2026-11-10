const KEY = "hp_token";

export const session = {
  get token(): string | null {
    return sessionStorage.getItem(KEY);
  },
  set(t: string) {
    sessionStorage.setItem(KEY, t);
  },
  clear() {
    sessionStorage.removeItem(KEY);
    // UI preferences that must last only for the logged-in session
    try {
      sessionStorage.removeItem(VISTA_KEY);
    } catch {
      /* storage unavailable */
    }
  },
};

// Chart granularity chosen on the dashboard: kept while the session lasts, reset on logout.
const VISTA_KEY = "hp_vista_grafico";
export const preferencias = {
  vistaGrafico(): VistaSerie | null {
    try {
      const v = sessionStorage.getItem(VISTA_KEY);
      return v && ["minuto", "hora", "dia", "3d", "5d"].includes(v) ? (v as VistaSerie) : null;
    } catch {
      return null;
    }
  },
  guardarVistaGrafico(v: VistaSerie) {
    try {
      sessionStorage.setItem(VISTA_KEY, v);
    } catch {
      /* storage unavailable */
    }
  },
};

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function api<T>(path: string, init: Omit<RequestInit, "body"> & { json?: unknown } = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (session.token) headers.set("Authorization", `Bearer ${session.token}`);
  let body: string | undefined;
  if (init.json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(init.json);
  }
  const r = await fetch(`/api/v1${path}`, { ...init, headers, body });
  if (r.status === 401 && !path.startsWith("/auth/login")) {
    session.clear();
    window.dispatchEvent(new Event("hp:logout"));
  }
  if (!r.ok) {
    let msg = r.statusText;
    try {
      const j = await r.json();
      msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail ?? j);
    } catch {
      /* sin cuerpo JSON */
    }
    throw new ApiError(r.status, msg);
  }
  return (await r.json()) as T;
}

// ------------------------------------------------------------------ tipos
export type Rol = "RESPONSABLE_SEGURIDAD" | "AUDITOR" | "ADMIN_INFRA";
export type Estado = "NUEVA" | "EN_REVISION" | "ARCHIVADA";

export interface Me {
  id: string;
  correo: string;
  rol: Rol;
}
export interface TokenOut {
  access_token: string;
  rol: Rol;
  correo: string;
}
export interface Kpi {
  valor: number;
  anterior: number;
  variacion_pct: number | null;
}
export interface TopIp {
  ip_origen: string;
  puntaje_asi: number;
  clasificacion: string;
  n_intentos: number;
  k_pares_distintos: number;
  fecha_calculo: string;
}
export interface Metricas {
  horas: number;
  sesiones: Kpi;
  ips_unicas: Kpi;
  intentos_login: Kpi;
  alertas_abiertas: number;
  comandos: number;
  serie: { hora: string; ssh: number; telnet: number }[];
  top_ips: TopIp[];
  subredes: { subred: string; sesiones: number }[];
  latencias: { ingesta_ms: number | null; veredicto_ms: number | null };
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
export interface Pagina<T> {
  total: number;
  limit: number;
  offset: number;
  items: T[];
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
export interface Usuario {
  id: string;
  correo: string;
  rol: Rol;
  estado: string;
  bloqueado_hasta: string | null;
  fecha_creacion: string;
}

// ------------------------------------------------------------------ laboratorio de ataques
export type Escenario =
  | "banner"
  | "manual"
  | "rafaga"
  | "persistente"
  | "stuffing"
  | "sigilosa"
  | "nmap-reconocimiento"
  | "hydra-stuffing"
  | "hydra-sigilosa"
  | "telnet-fuerza-bruta";
export type LabParam = "count" | "rate" | "tasks";
export interface LabEscenario {
  escenario: Escenario;
  comando: string;
  descripcion: string;
  duracion: string;
  editable: boolean;
  params: LabParam[];
  intento_s: number | null;
  count: number | null;
  rate: number | null;
  tasks: number | null;
}
export interface LabCatalogo {
  escenarios: LabEscenario[];
  limites: { count: [number, number]; rate: [number, number]; tasks: [number, number] };
}
export interface LabEstado {
  estado: "idle" | "running" | "stopping" | "finished" | "stopped" | "error";
  id?: number;
  escenario?: Escenario;
  count?: number | null;
  rate?: number | null;
  tasks?: number | null;
  inicio?: number;
  fin?: number | null;
  exit_code?: number | null;
  progreso?: { total: number; ok: number; fail: number; err: number };
  salida: string[];
}

// ------------------------------------------------------------------ perfil, serie, reinicio
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
export type VistaSerie = "minuto" | "hora" | "dia" | "3d" | "5d";
export interface SerieOut {
  vista: VistaSerie;
  paso_segundos: number;
  serie: { hora: string; ssh: number; telnet: number }[];
}
export interface ReinicioOut {
  eliminados: Record<string, number>;
}
