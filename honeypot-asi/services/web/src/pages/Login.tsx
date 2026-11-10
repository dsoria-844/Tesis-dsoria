import { useState, type FormEvent } from "react";
import { api, session, type Me, type TokenOut } from "../api";

export default function Login({ onLogin }: { onLogin: (m: Me) => void }) {
  const [correo, setCorreo] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      const t = await api<TokenOut>("/auth/login", { method: "POST", json: { correo, password } });
      session.set(t.access_token);
      onLogin(await api<Me>("/auth/me"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo iniciar sesión");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="login-shell">
      <section className="login-hero">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true" />
          Honeypot ASI
        </div>
        <div>
          <h1>
            Del ruido de ataques
            <br />a las alertas que importan.
          </h1>
          <p className="lead">
            Un honeypot registra cada intento de acceso y el Índice de Severidad de Ataque (ASI) separa la actividad
            crítica del ruido de fondo.
          </p>
        </div>
        <div className="formula">
          <span>ASI = 0,25·F + 0,30·V + 0,20·D + 0,25·P</span>
          <span>Alerta crítica con ASI ≥ 0,70 · ventanas de 15 y 60 min</span>
        </div>
      </section>
      <section className="login-main">
        <form className="login-form" onSubmit={enviar}>
          <div>
            <h2>Ingresar</h2>
            <p className="muted">Ingresá con tu usuario del laboratorio.</p>
          </div>
          <label className="campo">
            Correo
            <input
              type="email"
              autoComplete="username"
              value={correo}
              onChange={(e) => setCorreo(e.target.value)}
              required
              autoFocus
            />
          </label>
          <label className="campo">
            Contraseña
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          {error && (
            <div className="aviso aviso-error" role="alert">
              {error}
            </div>
          )}
          <button className="btn" disabled={enviando}>
            {enviando ? "Ingresando…" : "Ingresar"}
          </button>
          <p className="muted" style={{ fontSize: 13 }}>
            Tras 5 intentos fallidos el acceso se bloquea 15 minutos.
          </p>
          <p className="fine">
            Prototipo de Trabajo Final de Grado · Licenciatura en Seguridad Informática · Universidad Siglo 21
          </p>
        </form>
      </section>
    </div>
  );
}
