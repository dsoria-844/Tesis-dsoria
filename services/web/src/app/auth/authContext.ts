import { createContext } from "react";
import type { Me } from "./types";

export interface Ctx {
  me: Me;
  logout: () => void;
}
export const AuthCtx = createContext<Ctx | null>(null);
