import { Link, NavLink, useLocation } from "react-router-dom";
import { ROL } from "./auth/roles";
import type { Ctx } from "./auth/authContext";
import ThemeToggle from "./theme/ThemeToggle";

const iniciales = (correo: string) =>
  correo
    .replace(/[^a-zA-Z0-9]/g, "")
    .slice(0, 2)
    .toUpperCase() || "?";

export default function TopNav({ me, logout }: Ctx) {
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
