"use client";

import { ArrowLeftIcon, CopyIcon, DownloadIcon, MessageSquareIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { RichText } from "@/features/chat/markdown";
import { MermaidDiagram } from "@/features/chat/mermaid-diagram";
import { useCopyToClipboard } from "@/hooks/use-copy-to-clipboard";
import { api, errorMessage } from "@/lib/api/client";
import { useArtifactText } from "@/lib/api/queries";
import { useUiStore } from "@/stores/ui-store";

import { ArtifactIcon } from "./artifact-icon";
import { artifactCardId, type ChatArtifact } from "./chat-artifacts";

/** Lleva al artefacto en el chat: cierra el panel si está encima, lo desplaza a la vista y lo enfoca. */
function showInChat(name: string) {
  useUiStore.getState().setPanelSheetOpen(false);
  requestAnimationFrame(() => {
    const card = document.getElementById(artifactCardId(name));
    card?.scrollIntoView({ block: "center", behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    card?.focus({ preventScroll: true });
  });
}

/** Un artefacto en grande dentro del panel: vista previa, descarga, copia del código y salto al chat. */
export function ArtifactView({ item }: { item: ChatArtifact }) {
  const { artifact, question } = item;
  const { data, error, isPending } = useArtifactText(artifact.name);
  const { state, copy } = useCopyToClipboard();
  const title = artifact.title || artifact.name;
  const copyLabel = state === "copied" ? "Copiado" : state === "failed" ? "No se pudo copiar" : "Copiar código";

  return (
    <article className="flex flex-col gap-3" aria-label={title}>
      <Button variant="ghost" size="sm" className="-ml-2 self-start" onClick={() => useUiStore.getState().selectArtifact(null)}>
        <ArrowLeftIcon aria-hidden /> Todos los artefactos
      </Button>
      <header className="flex items-start gap-2">
        <ArtifactIcon type={artifact.type} />
        <div className="min-w-0">
          <h3 className="text-sm font-medium break-words">{title}</h3>
          <p className="font-mono text-xs break-all text-muted-foreground">{artifact.name}</p>
          {question && <p className="mt-1 text-xs break-words text-muted-foreground">Pedido con «{question}»</p>}
        </div>
      </header>
      <div className="flex flex-wrap gap-1.5">
        <Button asChild variant="outline" size="sm">
          {/* el backend responde con Content-Disposition: attachment */}
          <a href={api.artifactUrl(artifact.name)} download={artifact.name}>
            <DownloadIcon aria-hidden /> Descargar
          </a>
        </Button>
        <Button variant="outline" size="sm" disabled={!data} onClick={() => data && void copy(data)}>
          <CopyIcon aria-hidden /> {copyLabel}
        </Button>
        <Button variant="ghost" size="sm" onClick={() => showInChat(artifact.name)}>
          <MessageSquareIcon aria-hidden /> Ver en el chat
        </Button>
      </div>
      <div className="rounded-lg border bg-background/60 p-3">
        {isPending ? (
          <Skeleton className="h-48 w-full" />
        ) : error ? (
          <p className="text-sm text-muted-foreground">{errorMessage(error)}</p>
        ) : artifact.type === "mermaid" ? (
          <MermaidDiagram code={data} title={title} />
        ) : (
          <RichText text={data} className="text-sm" />
        )}
      </div>
    </article>
  );
}
