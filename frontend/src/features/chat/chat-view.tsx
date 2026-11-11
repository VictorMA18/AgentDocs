"use client";

import Link from "next/link";
import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useChatStream } from "@/hooks/use-chat-stream";
import { errorMessage } from "@/lib/api/client";
import { useConversation } from "@/lib/api/queries";
import { useChatStore } from "@/stores/chat-store";

import { Composer } from "./composer";
import { MessageList } from "./message-list";

function EmptyState() {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-2 px-4 py-16 text-center">
      <h2 className="font-heading text-xl font-medium">¿Qué quieres saber de tu documentación?</h2>
      <p className="text-sm text-muted-foreground">
        Sube un documento y pregunta sobre él. También puedes pedir un diagrama o los requisitos de una sección.
      </p>
    </div>
  );
}

/**
 * La conversación en pantalla. `conversationId = null` es una conversación nueva (ruta `/`); con un id
 * (ruta `/c/<id>`) se carga la guardada, salvo que ya esté en el store porque se acaba de crear aquí.
 */
export function ChatView({ conversationId }: { conversationId: string | null }) {
  const messages = useChatStore((state) => state.messages);
  const progress = useChatStore((state) => state.progress);
  const current = useChatStore((state) => state.sessionId);
  const { send, busy } = useChatStream();

  const needsLoad = conversationId !== null && current !== conversationId;
  const saved = useConversation(conversationId ?? "", needsLoad);

  // Ruta `/`: se empieza en limpio (si no hay un turno en curso, que es lo que acaba de navegar aquí).
  useEffect(() => {
    if (conversationId === null && !useChatStore.getState().busy) useChatStore.getState().reset();
  }, [conversationId]);

  // Ruta `/c/<id>`: cuando llega la conversación guardada, se vuelca en el store.
  useEffect(() => {
    if (needsLoad && saved.data) useChatStore.getState().load(saved.data.id, saved.data.turns);
  }, [needsLoad, saved.data]);

  let body: React.ReactNode;
  if (needsLoad && saved.isError) {
    body = (
      <div className="mx-auto flex max-w-md flex-col items-center gap-3 px-4 py-16 text-center">
        <p className="text-sm text-muted-foreground">{errorMessage(saved.error)}</p>
        <Button asChild variant="outline">
          <Link href="/">Empezar una conversación nueva</Link>
        </Button>
      </div>
    );
  } else if (needsLoad) {
    body = (
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-4 py-6" aria-busy="true">
        <Skeleton className="ml-auto h-10 w-1/2" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  } else if (messages.length === 0 && !progress) {
    body = <EmptyState />;
  } else {
    body = <MessageList messages={messages} progress={progress} />;
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto">{body}</div>
      <Composer onSend={(text) => void send(text)} disabled={busy || needsLoad} />
    </div>
  );
}
