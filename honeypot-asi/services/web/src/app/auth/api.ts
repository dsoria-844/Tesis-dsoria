import { api } from "../../shared/api/client";
import type { Me } from "./types";

export const obtenerMe = () => api<Me>("/auth/me");
