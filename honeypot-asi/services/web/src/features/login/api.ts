import { api } from "../../shared/api/client";
import type { TokenOut } from "./types";

export const iniciarSesion = (correo: string, password: string) =>
  api<TokenOut>("/auth/login", { method: "POST", json: { correo, password } });
