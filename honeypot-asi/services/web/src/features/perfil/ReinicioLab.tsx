import { useRef, useState, type FormEvent } from "react";
import { num } from "../../shared/lib/format";
import { reiniciarLaboratorio } from "./api";
import type { ReinicioOut } from "./types";

const ELIMINADO: Record<string, string> = {
  sesiones: "sesiones",
  intentos_login: "intentos de login",
  comandos_ejecutados: "comandos",
  evaluaciones_asi: "evaluaciones ASI",
  alertas_seguridad: "alertas",
  alertas_historial: "historial de alertas",
};

export default function ReinicioLab() {
  const ref = useRef<HTMLDialogElement>(null);
  const [texto, setTexto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [res, setRes] = useState<ReinicioOut | null>(null);

  const abrir = () => {
    setTexto("");
    setError(null);
    setRes(null);
    ref.current?.showModal();
  };
  const cerrar = () => ref.current?.close();

  const confirmar = async (e: FormEvent) => {
    e.preventDefault();
    if (texto !== "REINICIAR") return;
    setEnviando(true);
    setError(null);
    try {
      setRes(await reiniciarLaboratorio(texto));
      cerrar();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo reiniciar el laboratorio");
    } finally {
      setEnviando(false);
    }
  };

  return (
    <section className="card accion peligro" aria-labelledby="reinicio-h">
      <div>
        <h2 id="reinicio-h">Reiniciar laboratorio</h2>
        <p>
          Borra <b>definitivamente</b> sesiones, intentos de login, comandos, evaluaciones ASI, alertas y su historial
          para empezar una demostración limpia. Se conservan los usuarios, el registro de accesos (auditoría), los
          sensores y el avance de lectura del log, por lo que no se vuelve a importar lo ya procesado. La acción queda
          registrada. No se puede deshacer; solo para uso en laboratorio.
        </p>
        {res && (
          <div className="aviso aviso-ok" role="status" style={{ marginTop: 12 }}>
            Laboratorio reiniciado. Eliminados:{" "}
            {Object.entries(res.eliminados)
              .map(([k, v]) => `${num(v)} ${ELIMINADO[k] ?? k}`)
              .join(" · ")}
            .
          </div>
        )}
      </div>
      <button type="button" className="btn btn-peligro" onClick={abrir}>
        Confirmar
      </button>
      <dialog ref={ref} className="modal" aria-labelledby="reinicio-titulo">
        <form onSubmit={confirmar} className="form">
          <h2 id="reinicio-titulo">¿Reiniciar el laboratorio?</h2>
          <p className="muted">
            Esta acción no se puede deshacer. Para confirmar, escribí <code>REINICIAR</code>.
          </p>
          <label className="campo">
            Confirmación
            <input
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
              autoComplete="off"
              spellCheck={false}
              aria-describedby="reinicio-ayuda"
            />
          </label>
          <small id="reinicio-ayuda" className="muted">
            Se distingue entre mayúsculas y minúsculas.
          </small>
          {error && (
            <div className="aviso aviso-error" role="alert">
              {error}
            </div>
          )}
          <div className="acciones" style={{ justifyContent: "flex-end", marginTop: 0 }}>
            <button type="button" className="btn btn-ghost" onClick={cerrar}>
              Cancelar
            </button>
            <button type="submit" className="btn btn-peligro" disabled={texto !== "REINICIAR" || enviando}>
              {enviando ? "Reiniciando…" : "Borrar telemetría"}
            </button>
          </div>
        </form>
      </dialog>
    </section>
  );
}
