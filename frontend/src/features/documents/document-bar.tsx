"use client";

import { FileTextIcon, Loader2Icon } from "lucide-react";

import { FileTypeBadge } from "@/components/file-type";
import { Button } from "@/components/ui/button";
import { useDocuments } from "@/lib/api/queries";
import { plural } from "@/lib/labels";
import { useUiStore } from "@/stores/ui-store";
import { useUploadsFor } from "@/stores/upload-store";

import { AttachButton } from "./attach-button";

/**
 * Resumen de los documentos de la conversación encima de los mensajes, en una sola línea (Fase 12.C,
 * ADR-033): cuántos hay, sus tipos y lo que se está indexando. Pulsarlo abre la pestaña Documentos del
 * panel de la conversación, donde está la lista completa. Solo aparece cuando la conversación tiene algo.
 */
export function DocumentBar({ conversationId, busy }: { conversationId: string | null; busy: boolean }) {
  const { data } = useDocuments(conversationId);
  const uploads = useUploadsFor(conversationId);
  const docs = data ?? [];
  const visible = conversationId !== null && (docs.length > 0 || uploads.length > 0);
  // hasta tres tipos distintos como resumen (MD, PDF, PY…); la lista completa está en el panel
  const types = [...new Map(docs.map((d) => [d.source.slice(d.source.lastIndexOf(".")).toLowerCase(), d.source])).values()].slice(0, 3);

  return (
    <>
      {/* región estable (siempre montada): anuncia lo que se está indexando a los lectores de pantalla */}
      <p role="status" className="sr-only">
        {uploads.length ? `Indexando ${uploads.map((u) => u.name).join(", ")}` : ""}
      </p>
      {visible && (
        <div className="shrink-0 border-b px-4 py-1.5">
          <div className="mx-auto flex max-w-(--chat-w) items-center gap-2">
            {docs.length > 0 && (
              <Button
                variant="ghost"
                size="sm"
                className="min-w-0"
                aria-label={`Ver los documentos de esta conversación (${docs.length})`}
                onClick={() => useUiStore.getState().openPanel("documents")}
              >
                <FileTextIcon aria-hidden />
                {plural(docs.length, "documento", "documentos")}
                <span className="flex items-center gap-1" aria-hidden>
                  {types.map((name) => (
                    <FileTypeBadge key={name} name={name} />
                  ))}
                </span>
              </Button>
            )}
            {uploads.length > 0 && (
              <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <Loader2Icon className="size-3.5 animate-spin motion-reduce:animate-none" aria-hidden />
                Indexando {uploads.length === 1 ? uploads[0].name : plural(uploads.length, "documento", "documentos")}…
              </span>
            )}
            <span className="ml-auto">
              <AttachButton variant="inline" disabled={busy} />
            </span>
          </div>
        </div>
      )}
    </>
  );
}
