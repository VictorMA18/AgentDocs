"use client";

import { Loader2Icon, UploadIcon } from "lucide-react";
import { useId, useRef, useState, type DragEvent } from "react";

import { errorMessage } from "@/lib/api/client";
import { useUploadDocument } from "@/lib/api/queries";
import { plural } from "@/lib/labels";
import { notifyError, notifySuccess } from "@/lib/notify";

/** Zona para subir un documento (clic o arrastrar). El backend valida tipo y tamaño (415/413 legibles). */
export function UploadDropzone() {
  const upload = useUploadDocument();
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const inputId = useId(); // la barra lateral se pinta dos veces (escritorio y panel móvil): ids únicos

  function send(file: File | undefined) {
    if (!file || upload.isPending) return;
    upload.mutate(file, {
      onSuccess: (result) => {
        const warnings = result.warnings.length ? ` Avisos: ${result.warnings.join("; ")}` : "";
        notifySuccess(`${result.source} indexado: ${plural(result.chunks, "fragmento", "fragmentos")}.${warnings}`);
      },
      onError: (error) => notifyError(errorMessage(error)),
      onSettled: () => {
        if (input.current) input.current.value = "";
      },
    });
  }

  function onDrag(event: DragEvent, entering: boolean) {
    event.preventDefault();
    setOver(entering);
  }

  return (
    <label
      htmlFor={inputId}
      onDragEnter={(e) => onDrag(e, true)}
      onDragOver={(e) => onDrag(e, true)}
      onDragLeave={(e) => onDrag(e, false)}
      onDrop={(event) => {
        onDrag(event, false);
        send(event.dataTransfer.files[0]);
      }}
      // El input es invisible (sr-only): el anillo de foco se pinta en la zona cuando el input lo tiene.
      className={`flex cursor-pointer flex-col items-center gap-1 rounded-lg border border-dashed p-4 text-center transition-colors outline-none hover:bg-muted has-[:focus-visible]:border-ring has-[:focus-visible]:ring-3 has-[:focus-visible]:ring-ring/50 ${over ? "border-primary bg-muted" : ""}`}
    >
      {upload.isPending ? (
        <Loader2Icon className="size-5 animate-spin text-muted-foreground" aria-hidden />
      ) : (
        <UploadIcon className="size-5 text-muted-foreground" aria-hidden />
      )}
      <span className="text-sm font-medium">{upload.isPending ? "Indexando…" : "Subir documento"}</span>
      <span className="text-xs text-muted-foreground">Arrastra un archivo o haz clic</span>
      <input
        ref={input}
        id={inputId}
        type="file"
        className="sr-only"
        disabled={upload.isPending}
        onChange={(event) => send(event.target.files?.[0])}
      />
    </label>
  );
}
