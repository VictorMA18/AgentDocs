import { ChatView } from "@/features/chat/chat-view";

/** Conversación guardada: la URL identifica la conversación (recargar o compartir el enlace la reabre). */
export default async function ConversationPage({ params }: PageProps<"/c/[id]">) {
  const { id } = await params;
  return <ChatView conversationId={id} />;
}
