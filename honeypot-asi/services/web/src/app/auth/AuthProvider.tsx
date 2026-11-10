import type { ReactNode } from "react";
import { AuthCtx, type Ctx } from "./authContext";

export function AuthProvider({ me, logout, children }: Ctx & { children: ReactNode }) {
  return <AuthCtx.Provider value={{ me, logout }}>{children}</AuthCtx.Provider>;
}
