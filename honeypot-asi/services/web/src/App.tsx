import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { BrowserRouter, Link, Navigate, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { api, session, type Me, type Rol } from "./api";
import Actividad from "./pages/Actividad";
import Alerts from "./pages/Alerts";
import Dashboard from "./pages/Dashboard";
import IpDetalle from "./pages/IpDetalle";
import Lab from "./pages/Lab";

import Login from "./pages/Login";
import Perfil from "./pages/Perfil";
import Sessions from "./pages/Sessions";
import Users from "./pages/Users";

interface Ctx { me: Me; logout: () => void }
const AuthCtx = createContext<Ctx | null>(null);
export const useAuth = () => {
  const c = useContext(AuthCtx);
  if (!c) throw new Error("fuera de AuthCtx");
  return c;
};

export const ROL: Record<Rol, string> = {
  RESPONSABLE_SEGURIDAD: "Responsable de Seguridad",
  AUDITOR: "Auditor de Seguridad",
  ADMIN_INFRA: "Administrador de Infraestructura",
};

const TITULOS: [string, string][] = [
  ["/actividad", "Actividad por IP"], ["/ip/", "Detalle de IP"], ["/sesiones", "Sesiones y comandos"],
  ["/alertas", "Alertas y credenciales"], ["/usuarios", "Usuarios"], ["/laboratorio", "Laboratorio de ataques"],
  ["/perfil", "Mi perfil"],
];

function Topbar({ me, logout }: Ctx) {
  const { pathname } = useLocation();
  const titulo = TITULOS.find(([p]) => pathname.startsWith(p))?.[1] ?? "Panel general";
  return (
    <header className="topbar">
      <h2 className="topbar-titulo">{titulo}</h2>
      <div className="topbar-user">
        <Link to="/perfil" className="user-chip" title="Ver mi perfil">
          <span className="user-correo">{me.correo}</span>
          <small className="user-rol">{ROL[me.rol]}</small>
        </Link>
        <button type="button" className="icon-btn" onClick={logout} aria-label="Cerrar sesión" title="Cerrar sesión">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
            strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <polyline points="16 17 21 12 16 7" />
            <line x1="21" y1="12" x2="9" y2="12" />
          </svg>
        </button>
      </div>
    </header>
  );
}

function Shell({ me, logout }: Ctx) {
  const lee = me.rol !== "ADMIN_INFRA";
  return (
    <AuthCtx.Provider value={{ me, logout }}>
      <div className="app">
        <aside className="side">
          <div className="brand">
            <span className="dot" /> Honeypot <b>ASI</b>
          </div>
          <nav>
            <NavLink to="/" end>Panel general</NavLink>
            {lee && <NavLink to="/sesiones">Sesiones y comandos</NavLink>}
            {lee && <NavLink to="/alertas">Alertas y credenciales</NavLink>}
            {me.rol === "ADMIN_INFRA" && <NavLink to="/usuarios">Usuarios</NavLink>}
            {me.rol === "ADMIN_INFRA" && <NavLink to="/laboratorio">Laboratorio de ataques</NavLink>}
          </nav>
        </aside>
        <main className="main">
          <Topbar me={me} logout={logout} />
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
        </main>
      </div>
    </AuthCtx.Provider>
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
      api<Me>("/auth/me").then(setMe).catch(() => session.clear()).finally(() => setCargando(false));
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
