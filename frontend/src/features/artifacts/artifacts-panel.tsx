"use client";

import { ChevronRightIcon, ShapesIcon } from "lucide-react";
import { useMemo } from "react";

import type { Artifact } from "@/lib/api/schemas";
import { useChatStore } from "@/stores/chat-store";
import { useUiStore } from "@/stores/ui-store";

import { ArtifactIcon } from "./artifact-icon";
import { ArtifactView } from "./artifact-view";
import { chatArtifacts } from "./chat-artifacts";

const TYPE_LABEL: Record<Artifact["type"], string> = { mermaid: "Diagrama", requirements: "Requisitos" };

/**
 * Pestaña Artefactos del panel de la conversación (Fase 12.C, ADR-033): los diagramas y requisitos que
 * el agente ha generado en esta conversación, del más reciente al más antiguo. Al elegir uno se ve en
 * grande con su descarga, la copia del código y un salto a su tarjeta en el chat.
 */
export function ArtifactsPanel() {
  const messages = useChatStore((state) => state.messages);
  const selected = useUiStore((state) => state.selectedArtifact);
  const items = useMemo(() => chatArtifacts(messages), [messages]);
  const current = items.find((item) => item.artifact.name === selected);

  if (current) return <ArtifactView item={current} />;

  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed px-4 py-8 text-center">
        <ShapesIcon aria-hidden className="size-6 text-muted-foreground" />
        <p className="text-sm font-medium">Aún no hay artefactos en esta conversación</p>
        <p className="text-xs text-balance text-muted-foreground">
          Aquí aparecen los diagramas y los documentos de requisitos que genere el agente. Prueba con «Hazme un diagrama de
          secuencia de…» o «Escribe los requisitos de…».
        </p>
      </div>
    );
  }

  return (
    <ul className="flex flex-col gap-2" aria-label="Artefactos de esta conversación">
      {items.map(({ artifact, question }) => (
        <li key={artifact.name}>
          <button
            type="button"
            onClick={() => useUiStore.getState().selectArtifact(artifact.name)}
            className="flex w-full items-start gap-2 rounded-lg border bg-background/60 p-2 text-left transition-colors outline-none hover:bg-muted focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
          >
            <ArtifactIcon type={artifact.type} />
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-medium break-words">{artifact.title || artifact.name}</span>
              {/* la pregunta completa se lee en la vista del artefacto */}
              <span className="line-clamp-2 text-xs text-muted-foreground">
                {TYPE_LABEL[artifact.type]}
                {question && <> · «{question}»</>}
              </span>
            </span>
            <ChevronRightIcon aria-hidden className="mt-2 size-4 shrink-0 text-muted-foreground" />
          </button>
        </li>
      ))}
    </ul>
  );
}
