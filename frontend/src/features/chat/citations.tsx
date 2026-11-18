"use client";

import { useState } from "react";

import { FileTypeBadge } from "@/components/file-type";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Skeleton } from "@/components/ui/skeleton";
import { errorMessage } from "@/lib/api/client";
import { useFragment } from "@/lib/api/queries";
import { useChatStore } from "@/stores/chat-store";

import { RichText } from "./markdown";

// Citas interactivas (Fase 12.B, ADR-032). El agente cita los fragmentos como `[taskflow.md#4]`; un
// plugin de remark (sin dependencias) los convierte en un elemento <cite data-chunk> y `Citation` lo
// pinta como un botón que abre el texto del fragmento, pedido a la API de esa conversación.

/** `[archivo#n]` con el mismo nombre seguro que acepta la API (sin carpetas ni espacios). */
const CITATION = /\[([A-Za-z0-9._-]{1,100}#\d{1,6})\]/g;

type MdNode = { type: string; value?: string; children?: MdNode[]; data?: Record<string, unknown> };

/** Nodos donde una cita no se convierte: código, enlaces y sus definiciones. */
const SKIP = new Set(["code", "inlineCode", "link", "linkReference", "definition", "html"]);

/** Parte un texto en trozos de texto y nodos de cita. */
export function splitCitations(value: string): MdNode[] {
  const out: MdNode[] = [];
  let last = 0;
  for (const match of value.matchAll(CITATION)) {
    const start = match.index ?? 0;
    if (start > last) out.push({ type: "text", value: value.slice(last, start) });
    const chunk = match[1];
    out.push({
      type: "citation",
      data: { hName: "cite", hProperties: { dataChunk: chunk } },
      children: [{ type: "text", value: chunk }],
    });
    last = start + match[0].length;
  }
  if (last < value.length) out.push({ type: "text", value: value.slice(last) });
  return out.length ? out : [{ type: "text", value }];
}

function walk(node: MdNode): void {
  if (!node.children || SKIP.has(node.type)) return;
  node.children = node.children.flatMap((child) => {
    if (child.type === "text" && child.value) return splitCitations(child.value);
    walk(child);
    return [child];
  });
}

/** Plugin de remark: convierte las citas de los nodos de texto (no las del código ni las de los enlaces). */
export function remarkCitations() {
  return (tree: MdNode) => walk(tree);
}

/**
 * Una cita: chip con el tipo del documento, su nombre y el número de fragmento (contado desde 1 para
 * las personas; el id interno empieza en 0). Al pulsarlo muestra el texto del fragmento. Es contenido de
 * un documento (dato no confiable): pasa por el mismo Markdown saneado que las respuestas, nunca como HTML.
 */
export function Citation({ chunk }: { chunk: string }) {
  const conversationId = useChatStore((state) => state.sessionId);
  const [open, setOpen] = useState(false);
  const fragment = useFragment(conversationId, chunk, open);
  const at = chunk.lastIndexOf("#");
  const source = chunk.slice(0, at);
  const n = Number(chunk.slice(at + 1)) + 1;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          data-citation={chunk}
          aria-label={`Ver el fragmento ${n} de ${source}`}
          className="mx-0.5 inline-flex max-w-full items-baseline gap-1 rounded-md border bg-background/60 px-1 py-px align-baseline text-xs leading-5 not-italic transition-colors outline-none hover:bg-muted focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 aria-expanded:bg-muted"
        >
          <FileTypeBadge name={source} className="self-center" />
          <span className="break-all">{source}</span>
          <span className="text-muted-foreground tabular-nums">· {n}</span>
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-[min(28rem,calc(100vw-2rem))] gap-2 p-3">
        <p className="flex items-center gap-1.5 text-xs font-medium">
          <FileTypeBadge name={source} />
          <span className="break-all">{source}</span>
          <span className="text-muted-foreground">· fragmento {n}</span>
        </p>
        <div className="max-h-72 overflow-y-auto overscroll-contain">
          {fragment.isPending ? (
            <div className="space-y-2" aria-busy="true">
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-5/6" />
              <Skeleton className="h-3 w-2/3" />
            </div>
          ) : fragment.error ? (
            <p className="text-sm text-muted-foreground">{errorMessage(fragment.error)}</p>
          ) : (
            <RichText text={fragment.data.text} className="text-sm [&_:is(h1,h2,h3,h4)]:text-sm" />
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
