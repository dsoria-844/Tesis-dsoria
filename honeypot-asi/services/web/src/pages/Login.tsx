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
    <div className="centro">
      <form className="login card" onSubmit={enviar}>
        <div className="brand big">
          <span className="dot" /> Honeypot <b>ASI</b>
        </div>
        <p className="muted">Sistema de detección y análisis de ataques automatizados mediante señuelos de seguridad.</p>
        <label>
          Correo
          <input type="email" autoComplete="username" value={correo} onChange={(e) => setCorreo(e.target.value)} required autoFocus />
        </label>
        <label>
          Contraseña
          <input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </label>
        {error && <div className="aviso aviso-error">{error}</div>}
        <button className="btn" disabled={enviando}>{enviando ? "Ingresando…" : "Ingresar"}</button>
      </form>
    </div>
  );
}
