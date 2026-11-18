"use client";

import { Loader2Icon, XIcon } from "lucide-react";

import { ConfirmAction } from "@/components/confirm-action";
import { FileTypeBadge } from "@/components/file-type";
import { Button } from "@/components/ui/button";
import { errorMessage } from "@/lib/api/client";
import { useDeleteDocument } from "@/lib/api/queries";
import type { DocumentInfo } from "@/lib/api/schemas";
import { plural } from "@/lib/labels";
import { notifyError, notifySuccess } from "@/lib/notify";
import { useUiStore } from "@/stores/ui-store";

/**
 * Un documento de la conversación: tipo, nombre completo (se parte, nunca se corta: es la fuente de las
 * citas), fragmentos y «Quitar» con confirmación. Pulsar el nombre abre su vista previa. Lo usa la
 * pestaña Documentos del panel.
 */
export function DocumentItem({ conversationId, doc, busy }: { conversationId: string; doc: DocumentInfo; busy: boolean }) {
  const remove = useDeleteDocument();

  function onDelete() {
    remove.mutate(
      { conversationId, source: doc.source },
      {
        onSuccess: () => notifySuccess({ title: "Documento quitado", description: `${doc.source} ya no está en esta conversación.` }),
        onError: (err) => notifyError({ title: `No se pudo quitar ${doc.source}`, description: errorMessage(err) }),
      },
    );
  }

  return (
    <li className="flex items-start gap-2 rounded-lg border bg-background/60 p-2">
      <FileTypeBadge name={doc.source} className="mt-0.5" />
      <button
        type="button"
        onClick={() => useUiStore.getState().selectDocument(doc.source)}
        aria-label={`Ver ${doc.source}`}
        className="min-w-0 flex-1 rounded-sm text-left outline-none hover:underline focus-visible:ring-3 focus-visible:ring-ring/50"
      >
        <span className="block text-sm break-all">{doc.source}</span>
        <span className="block text-xs text-muted-foreground tabular-nums">{plural(doc.chunks, "fragmento", "fragmentos")} · ver</span>
      </button>
      <ConfirmAction
        title={`¿Quitar «${doc.source}» de esta conversación?`}
        description="El agente dejará de poder buscarlo y citarlo aquí. Para recuperarlo tendrás que volver a adjuntarlo."
        confirmLabel="Quitar documento"
        onConfirm={onDelete}
        trigger={
          <Button variant="ghost" size="icon-sm" aria-label={`Quitar ${doc.source}`} disabled={busy}>
            <XIcon aria-hidden />
          </Button>
        }
      />
    </li>
  );
}

/** Un documento que se está subiendo e indexando. */
export function UploadingItem({ name }: { name: string }) {
  return (
    <li className="flex items-start gap-2 rounded-lg border border-dashed p-2">
      <Loader2Icon className="mt-0.5 size-4 shrink-0 animate-spin text-muted-foreground motion-reduce:animate-none" aria-hidden />
      <span className="min-w-0 flex-1">
        <span className="block text-sm break-all">{name}</span>
        <span className="block text-xs text-muted-foreground">Indexando…</span>
      </span>
    </li>
  );
}
