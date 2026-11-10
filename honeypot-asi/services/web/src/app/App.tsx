import { useEffect, useState, type ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { session } from "../shared/api/session";
import Actividad from "../pages/Actividad";
import Alerts from "../pages/Alerts";
import Dashboard from "../pages/Dashboard";
import IpDetalle from "../pages/IpDetalle";
import Lab from "../pages/Lab";
import Login from "../pages/Login";
import Perfil from "../pages/Perfil";
import Sessions from "../pages/Sessions";
import Users from "../pages/Users";
import { obtenerMe } from "./auth/api";
import { AuthProvider } from "./auth/AuthProvider";
import type { Ctx } from "./auth/authContext";
import type { Me } from "./auth/types";
import TopNav from "./TopNav";

function Shell({ me, logout }: Ctx) {
  const lee = me.rol !== "ADMIN_INFRA";
  return (
    <AuthProvider me={me} logout={logout}>
      <TopNav me={me} logout={logout} />
      <main className="page">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/actividad" element={<Actividad />} />
          <Route path="/ip/:ip" element={<IpDetalle />} />
          <Route path="/sesiones" element={lee ? <Sessions /> : <Navigate to="/" />} />
          <Route path="/alertas" element={lee ? <Alerts /> : <Navigate to="/" />} />
          <Route path="/usuarios" element={me.rol === "ADMIN_INFRA" ? <Users /> : <Navigate to="/" />} />
          <Route path="/perfil" element={<Perfil />} />
          <Route path="/laboratorio" element={me.rol === "ADMIN_INFRA" ? <Lab /> : <Navigate to="/" />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
        <p className="foot-note">Laboratorio aislado sin salida a Internet</p>
      </main>
    </AuthProvider>
  );
}

export default function App(): ReactNode {
  const [me, setMe] = useState<Me | null>(null);
  const [cargando, setCargando] = useState(!!session.token);

  const logout = () => {
    session.clear();
    setMe(null);
  };

  useEffect(() => {
    const h = () => setMe(null);
    window.addEventListener("hp:logout", h);
    if (session.token) {
      obtenerMe()
        .then(setMe)
        .catch(() => session.clear())
        .finally(() => setCargando(false));
    }
    return () => window.removeEventListener("hp:logout", h);
  }, []);

  if (cargando) return <div className="centro">Cargando…</div>;
  if (!me) return <Login onLogin={setMe} />;
  return (
    <BrowserRouter>
      <Shell me={me} logout={logout} />
    </BrowserRouter>
  );
}
