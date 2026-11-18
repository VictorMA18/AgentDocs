import { cn } from "cn";
import { FileCodeIcon, FileIcon, FileJsonIcon, FileTextIcon, FileTypeIcon, type LucideIcon } from "lucide-react";

// Tipo de cada documento por su extensión (Fase 12.B). El tipo nunca va solo en el color: la etiqueta
// (MD, PDF, PY…) siempre está escrita. Los colores son tokens de globals.css (`.file-badge`), con un
// tono por familia y ninguno rojo, para no confundirse con el rojo de error.

export type FileFamily = "text" | "pdf" | "code" | "data" | "other";

const FAMILIES: Record<string, FileFamily> = {
  md: "text",
  txt: "text",
  pdf: "pdf",
  py: "code",
  js: "code",
  ts: "code",
  java: "code",
  json: "data",
  yaml: "data",
  yml: "data",
};

const ICONS: Record<FileFamily, LucideIcon> = {
  text: FileTextIcon,
  pdf: FileTypeIcon,
  code: FileCodeIcon,
  data: FileJsonIcon,
  other: FileIcon,
};

/** Extensiones que acepta la API (igual que ALLOWED_EXTENSIONS de backend/.env.example; el backend es quien valida). */
export const ACCEPTED_EXTENSIONS = Object.keys(FAMILIES).map((ext) => `.${ext}`);

/** Familia, etiqueta e icono de un archivo por su extensión («manual.PDF» → PDF). */
export function fileType(name: string): { family: FileFamily; label: string; icon: LucideIcon } {
  const dot = name.lastIndexOf(".");
  const ext = dot > 0 ? name.slice(dot + 1).toLowerCase() : "";
  const family = FAMILIES[ext] ?? "other";
  return { family, label: ext === "yml" ? "YAML" : ext ? ext.toUpperCase() : "ARCHIVO", icon: ICONS[family] };
}

/** Insignia con el icono y la etiqueta del tipo. Decorativa: el nombre del archivo va siempre al lado. */
export function FileTypeBadge({ name, className }: { name: string; className?: string }) {
  const { family, label, icon: Icon } = fileType(name);
  return (
    <span data-file={family} aria-hidden className={cn("file-badge", className)}>
      <Icon className="size-3" />
      {label}
    </span>
  );
}
