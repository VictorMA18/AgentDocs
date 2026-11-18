import type { Artifact } from "@/lib/api/schemas";
import type { ChatMessage } from "@/stores/chat-store";

/** Un artefacto de la conversación con la pregunta que lo generó. */
export type ChatArtifact = { artifact: Artifact; question: string };

/**
 * Artefactos de la conversación en pantalla, del más reciente al más antiguo. Salen de los turnos (cada
 * respuesta guardada trae su lista `artifacts`): no hace falta pedirlos a la API (ADR-033).
 */
export function chatArtifacts(messages: ChatMessage[]): ChatArtifact[] {
  const found: ChatArtifact[] = [];
  let question = "";
  for (const message of messages) {
    if (message.role === "user") question = message.text;
    else if (message.role === "agent") {
      for (const artifact of message.turn.artifacts) found.push({ artifact, question });
    }
  }
  return found.reverse();
}

/** Id del elemento de la tarjeta del artefacto en el chat (para «Ver en el chat»). */
export const artifactCardId = (name: string) => `artifact-${name}`;
