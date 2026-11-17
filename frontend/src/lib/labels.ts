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

/** Nombre del proveedor del LLM para mostrar (Fase 10). */
export const PROVIDER_LABELS: Record<string, string> = { claude: "Claude", gemini: "Gemini" };
export const providerLabel = (id: string) => PROVIDER_LABELS[id] ?? id;

export const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

export function formatDate(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? iso
    : date.toLocaleString("es", { dateStyle: "short", timeStyle: "short" });
}

export const DATE_GROUPS = ["Hoy", "Ayer", "Últimos 7 días", "Anteriores"] as const;
export type DateGroup = (typeof DATE_GROUPS)[number];

/**
 * Agrupa por la fecha de la última actividad, en días de calendario locales: Hoy, Ayer, Últimos 7 días
 * y Anteriores (en ese orden, sin grupos vacíos). Conserva el orden de entrada dentro de cada grupo.
 * Una fecha futura (reloj desajustado) cuenta como hoy; una ilegible, como anterior.
 */
export function groupByDate<T extends { updated: string }>(items: T[], now = new Date()): { label: DateGroup; items: T[] }[] {
  const startOfDay = (date: Date) => new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
  const today = startOfDay(now);
  const groups = new Map<DateGroup, T[]>(DATE_GROUPS.map((label) => [label, []]));
  for (const item of items) {
    const date = new Date(item.updated);
    const days = Number.isNaN(date.getTime()) ? Infinity : Math.round((today - startOfDay(date)) / 86_400_000);
    const label: DateGroup = days <= 0 ? "Hoy" : days === 1 ? "Ayer" : days <= 7 ? "Últimos 7 días" : "Anteriores";
    groups.get(label)!.push(item);
  }
  return DATE_GROUPS.map((label) => ({ label, items: groups.get(label)! })).filter((group) => group.items.length > 0);
}
