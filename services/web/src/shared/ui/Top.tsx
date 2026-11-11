import type { Conteo } from "../api/types";

export function Top({ titulo, filas }: { titulo: string; filas: Conteo[] }) {
  return (
    <div>
      <h3 className="muted" style={{ marginBottom: 10, fontSize: 13 }}>
        {titulo}
      </h3>
      {filas.length === 0 && <p className="muted">Sin datos.</p>}
      {filas.map((c) => (
        <div key={c.valor} className="fila-cred">
          <code title={c.valor}>{c.valor}</code>
          <span>{c.porcentaje}%</span>
        </div>
      ))}
    </div>
  );
}
