import { ChatView } from "@/features/chat/chat-view";

/** Conversación nueva: al enviar el primer mensaje la URL pasa a /c/<id>. */
export default function HomePage() {
  return <ChatView conversationId={null} />;
}
