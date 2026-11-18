"use client";

import { ArrowLeftIcon } from "lucide-react";

import { fileType, FileTypeBadge } from "@/components/file-type";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { RichText } from "@/features/chat/markdown";
import { errorMessage } from "@/lib/api/client";
import { useDocumentPreview } from "@/lib/api/queries";
import { plural } from "@/lib/labels";
import { useUiStore } from "@/stores/ui-store";

const CODE_LANG: Record<string, string> = { py: "python", js: "javascript", ts: "typescript", java: "java", json: "json", yaml: "yaml", yml: "yaml" };

/** Contenido de un fragmento según el tipo: Markdown saneado, código en un bloque o texto (PDF, TXT). */
function FragmentText({ source, text }: { source: string; text: string }) {
  const { family } = fileType(source);
  const ext = source.slice(source.lastIndexOf(".") + 1).toLowerCase();
  if (family === "code" || family === "data") {
    return <RichText text={"```" + (CODE_LANG[ext] ?? "") + "\n" + text.replaceAll("```", "ʼʼʼ") + "\n```"} className="text-sm" />;
  }
  if (ext === "md") return <RichText text={text} className="text-sm [&_:is(h1,h2,h3,h4)]:text-base" />;
  return <p className="text-sm leading-relaxed break-words whitespace-pre-wrap">{text}</p>;
}

/**
 * Vista previa de un documento de la conversación (Fase 12.C): sus fragmentos en orden, tal como los
 * indexó el agente y los puede citar («fragmento 3» es la cita [archivo#2]). Es contenido de un
 * documento (dato no confiable): pasa por el Markdown saneado o se pinta como texto, nunca como HTML.
 */
export function DocumentView({ conversationId, source }: { conversationId: string; source: string }) {
  const { data, error, isPending } = useDocumentPreview(conversationId, source);

  return (
    <article className="flex flex-col gap-3" aria-label={source}>
      <Button variant="ghost" size="sm" className="-ml-2 self-start" onClick={() => useUiStore.getState().selectDocument(null)}>
        <ArrowLeftIcon aria-hidden /> Todos los documentos
      </Button>
      <header className="flex items-start gap-2">
        <FileTypeBadge name={source} className="mt-0.5" />
        <div className="min-w-0">
          <h3 className="text-sm font-medium break-all">{source}</h3>
          {data && <p className="text-xs text-muted-foreground">{plural(data.chunks.length, "fragmento", "fragmentos")} · así lo lee el agente</p>}
        </div>
      </header>
      {isPending ? (
        <div className="flex flex-col gap-2" aria-busy="true">
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>
      ) : error ? (
        <p className="text-sm text-muted-foreground">{errorMessage(error)}</p>
      ) : (
        <ol className="flex flex-col gap-2" aria-label={`Fragmentos de ${source}`}>
          {data.chunks.map((chunk) => (
            <li key={chunk.id} className="rounded-lg border bg-background/60 p-3">
              <p className="mb-1.5 text-xs text-muted-foreground">
                Fragmento {chunk.n + 1}
                {chunk.section && <> · {chunk.section}</>}
              </p>
              <FragmentText source={source} text={chunk.text} />
            </li>
          ))}
        </ol>
      )}
    </article>
  );
}
