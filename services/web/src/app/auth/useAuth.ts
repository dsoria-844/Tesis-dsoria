import { useContext } from "react";
import { AuthCtx } from "./authContext";

export const useAuth = () => {
  const c = useContext(AuthCtx);
  if (!c) throw new Error("fuera de AuthCtx");
  return c;
};
