// Textos de la interfaz que dependen de datos.

/** Etiqueta legible de cada herramienta del agente (los nombres vienen de docs/04). */
export const TOOL_LABELS: Record<string, string> = {
  buscar_documentos: "Buscando en la documentación",
  listar_documentos: "Listando los documentos",
  generar_diagrama: "Generando el diagrama",
  generar_requisitos: "Generando los requisitos",
  cargar_guia: "Leyendo la guía de la skill",
};

export const toolLabel = (tool: string) => TOOL_LABELS[tool] ?? tool;

export const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

export function formatDate(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? iso
    : date.toLocaleString("es", { dateStyle: "short", timeStyle: "short" });
}
