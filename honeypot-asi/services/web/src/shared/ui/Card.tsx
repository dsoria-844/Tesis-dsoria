import type { ReactNode } from "react";

export function Card({
  titulo,
  extra,
  children,
  className = "",
}: {
  titulo?: string;
  extra?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`card ${className}`}>
      {(titulo || extra) && (
        <header className="card-h">
          <h2>{titulo}</h2>
          {extra}
        </header>
      )}
      {children}
    </section>
  );
}
