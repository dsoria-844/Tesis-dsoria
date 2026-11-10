import { useState } from "react";
import { fijarTema, temaActual, type Tema } from "./tema";

export default function ThemeToggle() {
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
