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
