"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useCallback } from "react";

import { errorMessage } from "@/lib/api/client";
import { queryKeys } from "@/lib/api/queries";
import { streamChat } from "@/lib/api/sse";
import { newSessionId, useChatStore } from "@/stores/chat-store";

/**
 * Envía un mensaje por /api/chat/stream y vuelca el progreso en el store.
 *
 * El turno escribe en el store (global) y no en el estado del componente: así sobrevive al cambio
 * de ruta de `/` a `/c/<id>` que ocurre al enviar el primer mensaje de una conversación nueva.
 */
export function useChatStream() {
  const client = useQueryClient();
  const router = useRouter();
  const busy = useChatStore((state) => state.busy);

  const send = useCallback(
    async (text: string) => {
      const store = useChatStore.getState();
      if (store.busy) return;
      const sessionId = store.sessionId ?? newSessionId();
      store.start(sessionId, text);
      if (store.sessionId === null) router.replace(`/c/${sessionId}`); // la conversación vive en la URL

      try {
        const turn = await streamChat({ session_id: sessionId, message: text }, (event) =>
          useChatStore.getState().advance(sessionId, event),
        );
        useChatStore.getState().finish(sessionId, turn);
      } catch (error) {
        useChatStore.getState().fail(sessionId, errorMessage(error));
      } finally {
        void client.invalidateQueries({ queryKey: queryKeys.conversations });
        // La copia en caché de esta conversación ya no tiene el último turno: al volver a abrirla se pide de nuevo.
        client.removeQueries({ queryKey: queryKeys.conversation(sessionId) });
      }
    },
    [client, router],
  );

  return { send, busy };
}
