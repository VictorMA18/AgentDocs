"use client";

import { FileTextIcon, UploadIcon } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState, type DragEvent } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { AttachButton } from "@/features/documents/attach-button";
import { DocumentBar } from "@/features/documents/document-bar";
import { useAttachDocuments } from "@/hooks/use-attach-documents";
import { useChatStream } from "@/hooks/use-chat-stream";
import { errorMessage } from "@/lib/api/client";
import { enter, useGSAP } from "@/lib/motion";
import { useConversation, useConversations, useDocuments } from "@/lib/api/queries";
import { useChatStore } from "@/stores/chat-store";
import { useUploadsFor } from "@/stores/upload-store";

import { Composer } from "./composer";
import { ProviderSelect } from "./provider-select";
import { MessageList } from "./message-list";

/** Preguntas de partida sobre los documentos de la conversación (Fase 12.B). */
export function suggestionsFor(subject: string): string[] {
  return [
    `Resume ${subject}`,
    `¿Qué conceptos clave explica ${subject}?`,
    `Hazme un diagrama de flujo de ${subject}`,
    `Escribe los requisitos funcionales de ${subject}`,
  ];
}

/**
 * Conversación sin mensajes. Sin documentos, invita a adjuntarlos (botón o soltarlos en el chat); con
 * documentos, propone preguntas de partida que se envían al pulsarlas. Sus piezas entran en escalón
 * (GSAP) cada vez que aparece.
 */
function EmptyState({
  conversationId,
  onPick,
  busy,
}: {
  conversationId: string | null;
  onPick: (text: string) => void;
  busy: boolean;
}) {
  const root = useRef<HTMLDivElement>(null);
  const { data } = useDocuments(conversationId);
  const uploads = useUploadsFor(conversationId);
  const docs = data ?? [];
  useGSAP(() => void enter(root.current!.querySelectorAll("[data-enter-item]")), { scope: root });

  const subject = docs.length === 1 ? docs[0].source : "los documentos";
  return (
    <div ref={root} className="mx-auto flex max-w-(--chat-w) flex-col items-center gap-2 px-4 py-16 text-center">
      <span data-enter-item className="mb-2 grid size-12 place-items-center rounded-2xl bg-primary/10 text-primary">
        <FileTextIcon aria-hidden className="size-6" />
      </span>
      {docs.length > 0 ? (
        <>
          <h2 data-enter-item className="font-heading text-xl font-medium text-balance">
            ¿Qué quieres saber de {docs.length === 1 ? <span className="break-all">{docs[0].source}</span> : "tus documentos"}?
          </h2>
          <p data-enter-item className="text-sm text-balance text-muted-foreground">
            Escribe tu pregunta o empieza por una de estas:
          </p>
          <ul data-enter-item aria-label="Preguntas sugeridas" className="mt-3 grid w-full gap-2 sm:grid-cols-2">
            {suggestionsFor(subject).map((text) => (
              <li key={text}>
                <Button
                  variant="outline"
                  disabled={busy}
                  onClick={() => onPick(text)}
                  className="h-auto min-h-11 w-full justify-start py-2 text-left whitespace-normal"
                >
                  <span className="break-words">{text}</span>
                </Button>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <>
          <h2 data-enter-item className="font-heading text-xl font-medium text-balance">
            ¿Qué quieres saber de tu documentación?
          </h2>
          <p data-enter-item className="max-w-md text-sm text-balance text-muted-foreground">
            {uploads.length > 0
              ? "Indexando tus documentos… En cuanto terminen podrás preguntar sobre ellos."
              : "Adjunta uno o varios documentos (Markdown, PDF, código, JSON o YAML) y pregunta sobre ellos. También puedes soltarlos aquí. Cada conversación tiene sus propios documentos."}
          </p>
          {uploads.length === 0 && (
            <div data-enter-item className="mt-3">
              <AttachButton variant="cta" disabled={busy} />
            </div>
          )}
        </>
      )}
    </div>
  );
}

/** ¿Lo que se arrastra trae archivos? (no reacciona a texto o enlaces arrastrados). */
const hasFiles = (event: DragEvent) => Array.from(event.dataTransfer.types).includes("Files");

/**
 * La conversación en pantalla. `conversationId = null` es una conversación nueva (ruta `/`); con un id
 * (ruta `/c/<id>`) se carga la guardada, salvo que ya esté en el store porque se acaba de crear aquí.
 */
export function ChatView({ conversationId }: { conversationId: string | null }) {
  const messages = useChatStore((state) => state.messages);
  const progress = useChatStore((state) => state.progress);
  const current = useChatStore((state) => state.sessionId);
  const { send, busy } = useChatStream();
  const attach = useAttachDocuments();
  const [dragging, setDragging] = useState(false);
  const dragDepth = useRef(0); // dragenter/dragleave saltan en cada hijo: se cuenta la profundidad

  const needsLoad = conversationId !== null && current !== conversationId;
  const saved = useConversation(conversationId ?? "", needsLoad);

  // Título de la pestaña: el de la conversación abierta (la lista ya está en caché por el lateral). Un
  // cambio de ruta en el cliente no lo actualiza solo, y así el título completo se puede leer aunque en
  // el lateral se corte. Con el componente <title> de React (lo sube a <head>), como indica la
  // documentación de Next para componentes de cliente; asignar document.title lo pisaba Next.
  const conversations = useConversations();
  const title = conversationId ? conversations.data?.find((c) => c.id === conversationId)?.title : undefined;

  // Ruta `/`: se empieza en limpio (si no hay un turno en curso, que es lo que acaba de navegar aquí).
  useEffect(() => {
    if (conversationId === null && !useChatStore.getState().busy) useChatStore.getState().reset();
  }, [conversationId]);

  // Ruta `/c/<id>`: cuando llega la conversación guardada, se vuelca en el store.
  useEffect(() => {
    if (needsLoad && saved.data) useChatStore.getState().load(saved.data.id, saved.data.turns, saved.data.provider);
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
      <div className="mx-auto flex w-full max-w-(--chat-w) flex-col gap-4 px-4 py-6" aria-busy="true">
        <Skeleton className="ml-auto h-10 w-1/2" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  } else if (messages.length === 0 && !progress) {
    body = <EmptyState conversationId={conversationId ?? current} onPick={(text) => void send(text)} busy={busy} />;
  } else {
    body = <MessageList messages={messages} progress={progress} />;
  }

  return (
    // Soltar archivos en cualquier parte del chat los adjunta a esta conversación. La capa que lo avisa
    // es un hermano posicionado, no un estilo del contenedor: nada de filter u opacity en un antecesor
    // del compositor (lo convertiría en backdrop root y su cristal dejaría de desenfocar).
    <div
      className="relative flex h-full flex-col"
      onDragEnter={(event) => {
        if (!hasFiles(event)) return;
        event.preventDefault();
        dragDepth.current += 1;
        setDragging(true);
      }}
      onDragOver={(event) => {
        if (hasFiles(event)) event.preventDefault();
      }}
      onDragLeave={(event) => {
        if (!hasFiles(event)) return;
        dragDepth.current = Math.max(0, dragDepth.current - 1);
        if (dragDepth.current === 0) setDragging(false);
      }}
      onDrop={(event) => {
        if (!hasFiles(event)) return;
        event.preventDefault();
        dragDepth.current = 0;
        setDragging(false);
        if (!busy) void attach(Array.from(event.dataTransfer.files));
      }}
    >
      <title>{title ? `${title} · TechDoc Agent` : "TechDoc Agent"}</title>
      <DocumentBar conversationId={conversationId ?? current} busy={busy} />
      {/* El compositor va pegado abajo (sticky) dentro de la zona que se desplaza: los mensajes pasan por
          detrás de él (en Glass se ven desenfocados a través del cristal) y, al final del todo, el último
          queda justo encima, sin tapar nada. */}
      <div className="min-h-0 flex-1 overflow-y-auto" data-chat-scroll>
        <div className="flex min-h-full flex-col">
          {/* role="log" en el contenedor que siempre existe: así los lectores de pantalla anuncian cada mensaje
              y cada paso nuevo (una región viva que se monta ya con su texto no se anuncia). */}
          <div className="flex-1" role="log" aria-label="Conversación">
            {body}
          </div>
          <Composer
            onSend={(text) => void send(text)}
            disabled={busy || needsLoad}
            footer={
              <div className="flex min-w-0 items-center gap-1">
                <AttachButton variant="icon" disabled={busy || needsLoad} />
                <ProviderSelect disabled={busy || needsLoad} />
              </div>
            }
          />
        </div>
      </div>
      {dragging && (
        <div
          aria-hidden
          className="pointer-events-none absolute inset-2 z-20 grid place-items-center rounded-xl border-2 border-dashed border-primary bg-background/85"
        >
          <p className="flex items-center gap-2 text-sm font-medium">
            <UploadIcon aria-hidden className="size-5" /> Suelta para añadir a esta conversación
          </p>
        </div>
      )}
    </div>
  );
}
