"use client";

import { Loader2Icon, UploadIcon } from "lucide-react";
import { useId, useRef, useState, type DragEvent } from "react";
import { toast } from "sonner";

import { errorMessage } from "@/lib/api/client";
import { useUploadDocument } from "@/lib/api/queries";

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
        toast.success(`${result.source} indexado: ${result.chunks} fragmentos.${warnings}`);
      },
      onError: (error) => toast.error(errorMessage(error)),
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
      className={`flex cursor-pointer flex-col items-center gap-1 rounded-lg border border-dashed p-4 text-center transition-colors hover:bg-muted ${over ? "border-primary bg-muted" : ""}`}
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
