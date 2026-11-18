"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useCallback } from "react";

import { api, errorMessage } from "@/lib/api/client";
import { queryKeys } from "@/lib/api/queries";
import { plural } from "@/lib/labels";
import { notifyError, notifySuccess, type Notice } from "@/lib/notify";
import { newSessionId, useChatStore } from "@/stores/chat-store";
import { useUiStore } from "@/stores/ui-store";
import { useUploadStore } from "@/stores/upload-store";

/**
 * Un aviso para todo lo que entró («Documento añadido · taskflow.md · 8 fragmentos» o «3 documentos
 * añadidos · a.md, b.md, c.md»), con la acción de verlos en el panel de la conversación.
 */
export function addedNotice(added: { source: string; chunks: number; warnings: string[] }[]): Notice {
  const warnings = added.flatMap((a) => a.warnings);
  const notes = warnings.length ? `. Avisos: ${warnings.join("; ")}` : "";
  const action = { label: "Ver documentos", onClick: () => useUiStore.getState().openPanel("documents") };
  if (added.length === 1) {
    const [doc] = added;
    return { title: "Documento añadido", description: `${doc.source} · ${plural(doc.chunks, "fragmento", "fragmentos")}${notes}`, action };
  }
  return { title: `${added.length} documentos añadidos`, description: `${added.map((a) => a.source).join(", ")}${notes}`, action };
}

/**
 * Adjunta documentos a la conversación abierta (clip, barra, estado vacío o soltar en el chat). En un
 * chat nuevo crea su id y, cuando el primer documento entra, pasa a `/c/<id>`: la conversación existe
 * desde su primer documento. Si no entra ninguno, el chat nuevo queda como estaba. Los archivos se
 * suben de uno en uno. Cada error avisa enseguida (dice qué falló); los que entran se avisan juntos al
 * final, en un solo aviso, para no apilar uno por archivo encima de la barra de documentos.
 *
 * Llama al cliente directamente (no a un useMutation): la vista se desmonta al cambiar de ruta y la
 * subida tiene que terminar igual.
 */
export function useAttachDocuments() {
  const client = useQueryClient();
  const router = useRouter();

  return useCallback(
    async (files: File[]) => {
      if (files.length === 0) return;
      const chat = useChatStore.getState();
      const isNew = chat.sessionId === null;
      const conversationId = chat.sessionId ?? newSessionId();
      if (isNew) {
        chat.load(conversationId, [], chat.provider); // la vista ya muestra el «Indexando…»
        chat.adoptDraft(conversationId); // lo que se estaba escribiendo sigue en el compositor
      }
      const uploads = useUploadStore.getState();
      const added: { source: string; chunks: number; warnings: string[] }[] = [];
      for (const file of files) {
        const upload = uploads.add(conversationId, file.name);
        try {
          const result = await api.uploadDocument({ conversationId, file });
          if (window.location.pathname !== `/c/${conversationId}`) router.replace(`/c/${conversationId}`);
          added.push(result);
        } catch (error) {
          notifyError({ title: `No se pudo añadir ${file.name}`, description: errorMessage(error) });
        } finally {
          uploads.remove(upload);
          await client.invalidateQueries({ queryKey: queryKeys.documents(conversationId) });
          // subir otra vez el mismo nombre reemplaza el documento: su vista previa y sus citas cambian
          void client.invalidateQueries({ queryKey: ["document-preview", conversationId] });
          void client.invalidateQueries({ queryKey: ["fragment", conversationId] });
          void client.invalidateQueries({ queryKey: queryKeys.conversations });
        }
      }
      if (added.length > 0) notifySuccess(addedNotice(added));
      // Chat nuevo sin ningún documento: vuelve a ser un chat nuevo (sin id), salvo que ya se haya escrito.
      const now = useChatStore.getState();
      if (isNew && added.length === 0 && now.sessionId === conversationId && now.messages.length === 0 && !now.busy) now.reset();
    },
    [client, router],
  );
}
