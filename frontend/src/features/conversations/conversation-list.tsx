"use client";

import { Trash2Icon } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import { ConfirmAction } from "@/components/confirm-action";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { errorMessage } from "@/lib/api/client";
import { useConversations, useDeleteConversation } from "@/lib/api/queries";
import { notifyError, notifySuccess } from "@/lib/notify";
import { formatDate, plural } from "@/lib/labels";
import { useChatStore } from "@/stores/chat-store";
import { useUiStore } from "@/stores/ui-store";

/** Conversaciones guardadas: abrir (enlace a /c/<id>) y quitar. Bloqueadas mientras hay un turno en curso. */
export function ConversationList() {
  const { data, error, isPending } = useConversations();
  const remove = useDeleteConversation();
  const busy = useChatStore((state) => state.busy);
  const params = useParams<{ id?: string }>();
  const router = useRouter();
  const closeSidebar = () => useUiStore.getState().setSidebarOpen(false);

  function onDelete(id: string, title: string) {
    remove.mutate(id, {
      onSuccess: () => {
        notifySuccess(`Conversación «${title}» quitada.`);
        if (id === params.id) {
          useChatStore.getState().reset();
          router.push("/");
        }
      },
      onError: (err) => notifyError(errorMessage(err)),
    });
  }

  if (isPending) {
    return (
      <div className="space-y-2" aria-busy="true">
        <Skeleton className="h-10" />
        <Skeleton className="h-10" />
      </div>
    );
  }
  if (error) return <p className="text-sm text-destructive">{errorMessage(error)}</p>;
  if (data.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Aún no hay conversaciones guardadas. Se guardan solas al enviar el primer mensaje.
      </p>
    );
  }
  return (
    <ul className="space-y-1" aria-label="Conversaciones guardadas">
      {data.map((conv) => {
        const current = conv.id === params.id;
        return (
          <li
            key={conv.id}
            className={`group flex items-center gap-1 rounded-md pr-1 hover:bg-muted ${current ? "bg-muted" : ""}`}
          >
            <Link
              href={`/c/${conv.id}`}
              aria-current={current ? "page" : undefined}
              aria-disabled={busy}
              tabIndex={busy ? -1 : undefined}
              onClick={(event) => (busy ? event.preventDefault() : closeSidebar())}
              className={`min-w-0 flex-1 px-2 py-1.5 ${busy ? "pointer-events-none opacity-60" : ""}`}
            >
              <span className="block truncate text-sm">{conv.title}</span>
              <span className="block text-xs text-muted-foreground">
                {plural(conv.turns, "pregunta", "preguntas")} · {formatDate(conv.updated)}
              </span>
            </Link>
            <ConfirmAction
              title={`¿Quitar la conversación «${conv.title}»?`}
              description="Se borrarán sus mensajes y lo que el agente recuerda de ella. No se puede deshacer."
              confirmLabel="Quitar conversación"
              onConfirm={() => onDelete(conv.id, conv.title)}
              trigger={
                <Button
                  variant="ghost"
                  size="icon-sm"
                  disabled={busy}
                  aria-label={`Quitar la conversación ${conv.title}`}
                  className="opacity-60 group-hover:opacity-100"
                >
                  <Trash2Icon aria-hidden />
                </Button>
              }
            />
          </li>
        );
      })}
    </ul>
  );
}
