export function Barra({ valor, max = 1, color = "var(--accent)" }: { valor: number; max?: number; color?: string }) {
  const pct = Math.max(0, Math.min(100, (valor / (max || 1)) * 100));
  return (
    <div className="barra">
      <div style={{ width: `${pct}%`, background: color }} />
    </div>
  );
}
