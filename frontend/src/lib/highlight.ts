// Coincidencias de búsqueda sin distinguir mayúsculas ni tildes (como el backend, core/transcripts.py),
// devueltas en posiciones del texto original para poder resaltarlas.

function fold(text: string): { folded: string; positions: number[] } {
  let folded = "";
  const positions: number[] = [];
  Array.from(text).forEach((char, index) => {
    for (const part of char.normalize("NFD").replace(/\p{M}/gu, "").toLocaleLowerCase("es")) {
      folded += part;
      positions.push(index);
    }
  });
  return { folded, positions };
}

/** Primera aparición de `query` en `text` como `[inicio, fin)` del texto original, o `null`. */
export function findMatch(text: string, query: string): [number, number] | null {
  const needle = fold(query.trim().replace(/\s+/g, " ")).folded;
  if (!needle) return null;
  const { folded, positions } = fold(text);
  const at = folded.indexOf(needle);
  if (at < 0) return null;
  const chars = Array.from(text);
  const start = positions[at];
  const end = positions[at + needle.length - 1] + 1;
  // posiciones en caracteres (Array.from) → en unidades de string
  return [chars.slice(0, start).join("").length, chars.slice(0, end).join("").length];
}
