export function Estado404({ error }: { error: string | null }) {
  return error ? <div className="aviso aviso-error">{error}</div> : null;
}
