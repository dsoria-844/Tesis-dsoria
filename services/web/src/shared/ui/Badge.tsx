import { ETIQUETA } from "../lib/severity";

export function Badge({ clase, large = false }: { clase: string; large?: boolean }) {
  return <span className={`badge ${clase.toLowerCase()}${large ? " lg" : ""}`}>{ETIQUETA[clase] ?? clase}</span>;
}
