"use client";

import { FileIcon, Trash2Icon } from "lucide-react";

import { ConfirmAction } from "@/components/confirm-action";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { errorMessage } from "@/lib/api/client";
import { useDeleteDocument, useDocuments } from "@/lib/api/queries";
import { notifyError, notifySuccess } from "@/lib/notify";
import { plural } from "@/lib/labels";

/** Documentos indexados con su número de fragmentos; se pueden quitar del índice. */
export function DocumentList() {
  const { data, error, isPending } = useDocuments();
  const remove = useDeleteDocument();

  function onDelete(source: string) {
    remove.mutate(source, {
      onSuccess: () => notifySuccess(`${source} quitado del índice.`),
      onError: (err) => notifyError(errorMessage(err)),
    });
  }

  if (isPending) {
    return (
      <div className="space-y-2" aria-busy="true">
        <Skeleton className="h-8" />
        <Skeleton className="h-8" />
      </div>
    );
  }
  if (error) return <p className="text-sm text-destructive">{errorMessage(error)}</p>;
  if (data.length === 0) return <p className="text-sm text-muted-foreground">Aún no hay documentos indexados.</p>;

  return (
    <ul className="space-y-1" aria-label="Documentos indexados">
      {data.map((doc) => (
        <li key={doc.source} className="group flex items-center gap-2 rounded-md px-2 py-1 hover:bg-muted">
          <FileIcon className="size-4 shrink-0 text-muted-foreground" aria-hidden />
          <span className="min-w-0 flex-1">
            {/* Sin truncar: el nombre completo es la fuente de las citas y no se muestra en otro sitio. */}
            <span className="block text-sm break-all">{doc.source}</span>
            <span className="block text-xs text-muted-foreground">{plural(doc.chunks, "fragmento", "fragmentos")}</span>
          </span>
          <ConfirmAction
            title={`¿Quitar «${doc.source}» del índice?`}
            description="El agente dejará de poder buscarlo y citarlo. Para recuperarlo tendrás que volver a subirlo."
            confirmLabel="Quitar documento"
            onConfirm={() => onDelete(doc.source)}
            trigger={
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label={`Quitar ${doc.source}`}
                className="opacity-60 group-hover:opacity-100"
              >
                <Trash2Icon aria-hidden />
              </Button>
            }
          />
        </li>
      ))}
    </ul>
  );
}
