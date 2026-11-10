export function Estado({ e }: { e: string }) {
  return (
    <span className={`tag estado-${e.toLowerCase()}`}>{e.charAt(0) + e.slice(1).toLowerCase().replace("_", " ")}</span>
  );
}
