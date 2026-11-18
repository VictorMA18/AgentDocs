"use client";

import { DownloadIcon, FileTextIcon, PanelRightOpenIcon, WorkflowIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { artifactCardId } from "@/features/artifacts/chat-artifacts";
import { api, errorMessage } from "@/lib/api/client";
import { useArtifactText } from "@/lib/api/queries";
import type { Artifact } from "@/lib/api/schemas";
import { useUiStore } from "@/stores/ui-store";

import { RichText } from "./markdown";
import { MermaidDiagram } from "./mermaid-diagram";

/**
 * Diagrama o documento de requisitos guardado en un turno: vista previa, descarga y «Abrir en el panel»
 * (lo muestra en grande en la pestaña Artefactos, Fase 12.C). Enfocable por id para «Ver en el chat».
 */
export function ArtifactCard({ artifact }: { artifact: Artifact }) {
  const { data, error, isPending } = useArtifactText(artifact.name);
  const Icon = artifact.type === "mermaid" ? WorkflowIcon : FileTextIcon;

  return (
    <Card size="sm" className="mt-3 outline-none focus-visible:ring-3 focus-visible:ring-ring/50" data-testid="artifact" id={artifactCardId(artifact.name)} tabIndex={-1}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Icon className="size-4 text-muted-foreground" aria-hidden />
          {artifact.title || artifact.name}
        </CardTitle>
        <CardDescription className="font-mono text-xs">{artifact.name}</CardDescription>
        <CardAction className="flex gap-1.5">
          <Button
            variant="ghost"
            size="sm"
            aria-label={`Abrir en el panel: ${artifact.title || artifact.name}`}
            onClick={() => useUiStore.getState().openPanel("artifacts", artifact.name)}
          >
            <PanelRightOpenIcon aria-hidden />
            <span className="hidden sm:inline">Abrir en el panel</span>
          </Button>
          <Button asChild variant="outline" size="sm">
            {/* El backend responde con Content-Disposition: attachment, así que descarga aunque sea otro origen. */}
            <a href={api.artifactUrl(artifact.name)} download={artifact.name}>
              <DownloadIcon aria-hidden />
              Descargar
            </a>
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent>
        {isPending ? (
          <Skeleton className="h-24 w-full" />
        ) : error ? (
          <p className="text-sm text-muted-foreground">{errorMessage(error)}</p>
        ) : artifact.type === "mermaid" ? (
          <MermaidDiagram code={data} title={artifact.title || artifact.name} />
        ) : (
          <RichText text={data} />
        )}
      </CardContent>
    </Card>
  );
}
