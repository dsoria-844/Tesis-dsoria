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
import { fijarTema, temaActual, type Tema } from "./tema";

interface Ctx {
  me: Me;
  logout: () => void;
}
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

const iniciales = (correo: string) =>
  correo
    .replace(/[^a-zA-Z0-9]/g, "")
    .slice(0, 2)
    .toUpperCase() || "?";

function ThemeToggle() {
  const [tema, setTema] = useState<Tema>(temaActual);
  const oscuro = tema === "dark";
  const etiqueta = oscuro ? "Activar tema claro" : "Activar tema oscuro";
  const alternar = () => {
    const t: Tema = oscuro ? "light" : "dark";
    fijarTema(t);
    setTema(t);
  };
  return (
    <button
      type="button"
      className="icon-btn theme-btn"
      onClick={alternar}
      aria-label={etiqueta}
      aria-pressed={oscuro}
      title={etiqueta}
    >
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        {oscuro ? (
          <>
            <circle cx="12" cy="12" r="4" />
            <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
          </>
        ) : (
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
        )}
      </svg>
    </button>
  );
}

function TopNav({ me, logout }: Ctx) {
  const { pathname } = useLocation();
  const lee = me.rol !== "ADMIN_INFRA";
  // The IP detail page belongs to the "Actividad" section.
  const actividadActiva = pathname.startsWith("/actividad") || pathname.startsWith("/ip/");
  return (
    <header className="topnav">
      <div className="topnav-in">
        <Link to="/" className="brand">
          <span className="brand-mark" aria-hidden="true" />
          Honeypot ASI
        </Link>
        <nav className="navlinks" aria-label="Secciones">
          <NavLink to="/" end>
            Resumen
          </NavLink>
          <NavLink to="/actividad" className={actividadActiva ? "active" : ""}>
            Actividad
          </NavLink>
          {lee && <NavLink to="/sesiones">Sesiones</NavLink>}
          {lee && <NavLink to="/alertas">Alertas</NavLink>}
          {!lee && <NavLink to="/laboratorio">Laboratorio</NavLink>}
          {!lee && <NavLink to="/usuarios">Usuarios</NavLink>}
        </nav>
        <div className="topnav-end">
          <span className="pill">Prototipo · entorno aislado</span>
          <ThemeToggle />
          <Link
            to="/perfil"
            className="avatar"
            aria-label={`Mi perfil (${me.correo})`}
            title={`${me.correo} · ${ROL[me.rol]}`}
          >
            {iniciales(me.correo)}
          </Link>
          <button type="button" className="icon-btn" onClick={logout} aria-label="Cerrar sesión" title="Cerrar sesión">
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
              <polyline points="16 17 21 12 16 7" />
              <line x1="21" y1="12" x2="9" y2="12" />
            </svg>
          </button>
        </div>
      </div>
    </header>
  );
}

function Shell({ me, logout }: Ctx) {
  const lee = me.rol !== "ADMIN_INFRA";
  return (
    <AuthCtx.Provider value={{ me, logout }}>
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
      api<Me>("/auth/me")
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
