"use client";

import type { ComponentProps } from "react";
import Markdown, { type Components, type ExtraProps } from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";

import { Button } from "@/components/ui/button";
import { useCopyToClipboard } from "@/hooks/use-copy-to-clipboard";

// La salida del modelo es texto de un desconocido: react-markdown construye elementos de React
// (nunca innerHTML) y rehype-sanitize quita lo que no esté en la lista de GitHub (scripts, on*=, style…).

type HastNode = { type: string; value?: string; children?: HastNode[] };

/** Texto plano de un nodo del árbol HTML (para copiar un bloque de código tal cual). */
function nodeText(node: HastNode | undefined): string {
  if (!node) return "";
  if (node.type === "text") return node.value ?? "";
  return (node.children ?? []).map(nodeText).join("");
}

function CodeBlock({ node, children, ...props }: ComponentProps<"pre"> & ExtraProps) {
  const { state, copy } = useCopyToClipboard();
  const label = state === "copied" ? "Copiado" : state === "failed" ? "No se pudo copiar" : "Copiar";
  return (
    <div className="group relative">
      <pre {...props}>{children}</pre>
      <Button
        type="button"
        variant="secondary"
        size="xs"
        className="absolute top-2 right-2 opacity-80 group-hover:opacity-100"
        onClick={() => void copy(nodeText(node as HastNode | undefined))}
      >
        {label}
      </Button>
    </div>
  );
}

const components: Components = {
  pre: CodeBlock,
  a: ({ node: _node, ...props }) => <a {...props} target="_blank" rel="noopener noreferrer" />,
};

export function RichText({ text }: { text: string }) {
  return (
    <div className="prose-chat">
      <Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]} components={components}>
        {text}
      </Markdown>
    </div>
  );
}
