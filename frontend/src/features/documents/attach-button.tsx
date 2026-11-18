"use client";

import { PaperclipIcon, PlusIcon } from "lucide-react";
import { useRef, type ReactNode } from "react";

import { ACCEPTED_EXTENSIONS } from "@/components/file-type";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useAttachDocuments } from "@/hooks/use-attach-documents";

const ACCEPT = ACCEPTED_EXTENSIONS.join(",");
export const TYPES_HINT = "Markdown, texto, PDF, código (Python, JavaScript, TypeScript, Java), JSON o YAML";

/**
 * Abre el selector de archivos y adjunta lo elegido a la conversación abierta (varios a la vez). Tres
 * formas: `icon` (el clip del compositor, con tooltip), `inline` (el «Añadir» de la barra) y `cta` (el
 * botón del estado vacío). `accept` solo filtra el selector: la API es quien valida.
 */
export function AttachButton({ variant, disabled = false }: { variant: "icon" | "inline" | "cta"; disabled?: boolean }) {
  const input = useRef<HTMLInputElement>(null);
  const attach = useAttachDocuments();
  const label = "Adjuntar documentos";
  const open = () => input.current?.click();

  let button: ReactNode;
  if (variant === "icon") {
    button = (
      <Tooltip>
        <TooltipTrigger asChild>
          <Button type="button" variant="ghost" size="icon-sm" aria-label={label} disabled={disabled} onClick={open}>
            <PaperclipIcon aria-hidden />
          </Button>
        </TooltipTrigger>
        <TooltipContent>{label}</TooltipContent>
      </Tooltip>
    );
  } else if (variant === "inline") {
    button = (
      <Button type="button" variant="ghost" size="xs" disabled={disabled} onClick={open} aria-label="Añadir documentos">
        <PlusIcon aria-hidden /> Añadir
      </Button>
    );
  } else {
    button = (
      <Button type="button" variant="outline" disabled={disabled} onClick={open}>
        <PaperclipIcon aria-hidden /> {label}
      </Button>
    );
  }
  return (
    <>
      {/* fuera del orden de tabulación: se abre con el botón */}
      <input
        ref={input}
        type="file"
        multiple
        accept={ACCEPT}
        className="sr-only"
        tabIndex={-1}
        aria-hidden
        data-attach-input
        onChange={(event) => {
          const files = Array.from(event.target.files ?? []);
          event.target.value = ""; // permite volver a elegir el mismo archivo
          void attach(files);
        }}
      />
      {button}
    </>
  );
}
