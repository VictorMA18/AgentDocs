"use client";

import { FileTextIcon } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";
import { useDocuments } from "@/lib/api/queries";
import { plural } from "@/lib/labels";
import { useChatStore } from "@/stores/chat-store";
import { useUiStore } from "@/stores/ui-store";
import { useUploadsFor } from "@/stores/upload-store";

import { AttachButton } from "./attach-button";
import { DocumentItem, UploadingItem } from "./document-item";
import { DocumentView } from "./document-view";

/** Pestaña Documentos del panel de la conversación (Fase 12.C): los de esta conversación y lo que se indexa. */
export function DocumentsPanel() {
  const conversationId = useChatStore((state) => state.sessionId);
  const busy = useChatStore((state) => state.busy);
  const { data, isPending } = useDocuments(conversationId);
  const uploads = useUploadsFor(conversationId);
  const docs = data ?? [];
  const empty = docs.length === 0 && uploads.length === 0;
  const selected = useUiStore((state) => state.selectedDocument);

  if (conversationId && selected && docs.some((d) => d.source === selected)) {
    return <DocumentView conversationId={conversationId} source={selected} />;
  }

  if (conversationId && isPending) {
    return (
      <div className="flex flex-col gap-2" aria-busy="true">
        <Skeleton className="h-14" />
        <Skeleton className="h-14" />
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          {empty ? "El agente solo busca en los documentos de esta conversación." : plural(docs.length, "documento", "documentos")}
        </p>
        {!empty && <AttachButton variant="inline" disabled={busy} />}
      </div>
      {empty ? (
        <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed px-4 py-8 text-center">
          <FileTextIcon aria-hidden className="size-6 text-muted-foreground" />
          <p className="text-sm font-medium">Esta conversación no tiene documentos</p>
          <p className="text-xs text-balance text-muted-foreground">
            Adjúntalos con el clip, desde aquí o soltándolos en el chat. Markdown, PDF, código, JSON o YAML.
          </p>
          <AttachButton variant="cta" disabled={busy} />
        </div>
      ) : (
        <ul className="flex flex-col gap-2" aria-label="Documentos de esta conversación">
          {docs.map((doc) => (
            <DocumentItem key={doc.source} conversationId={conversationId!} doc={doc} busy={busy} />
          ))}
          {uploads.map((upload) => (
            <UploadingItem key={upload.id} name={upload.name} />
          ))}
        </ul>
      )}
    </div>
  );
}
