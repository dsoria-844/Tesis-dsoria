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

export type VistaSerie = "minuto" | "hora" | "dia" | "3d" | "5d";

export interface SerieOut {
  vista: VistaSerie;
  paso_segundos: number;
  serie: { hora: string; ssh: number; telnet: number }[];
}
