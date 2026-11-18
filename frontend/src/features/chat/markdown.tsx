"use client";

import type { ComponentProps } from "react";
import Markdown, { type Components, type ExtraProps } from "react-markdown";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";
import remarkGfm from "remark-gfm";

import { Button } from "@/components/ui/button";
import { useCopyToClipboard } from "@/hooks/use-copy-to-clipboard";

import { Citation, remarkCitations } from "./citations";

// La salida del modelo es texto de un desconocido: react-markdown construye elementos de React
// (nunca innerHTML) y rehype-sanitize quita lo que no esté en la lista de GitHub (scripts, on*=, style…).
// A esa lista solo se añade el <cite data-chunk> de las citas (lo genera remarkCitations, no el modelo).
const schema = {
  ...defaultSchema,
  tagNames: [...(defaultSchema.tagNames ?? []), "cite"],
  attributes: { ...defaultSchema.attributes, cite: ["dataChunk"] },
};

type HastNode = { type: string; value?: string; children?: HastNode[]; properties?: { className?: unknown } };

/** Texto plano de un nodo del árbol HTML (para copiar un bloque de código tal cual). */
function nodeText(node: HastNode | undefined): string {
  if (!node) return "";
  if (node.type === "text") return node.value ?? "";
  return (node.children ?? []).map(nodeText).join("");
}

/** ¿Es un bloque ```mermaid? (rehype-sanitize conserva la clase language-* del <code>). */
function isMermaid(node: HastNode | undefined): boolean {
  const className = node?.children?.[0]?.properties?.className;
  return Array.isArray(className) && className.includes("language-mermaid");
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

/**
 * Con el diagrama ya dibujado debajo (tarjeta del artefacto), su código Mermaid se pliega: sigue a mano
 * (y se puede copiar) sin repetirse en grande justo encima de la vista previa.
 */
function FoldedMermaid(props: ComponentProps<"pre"> & ExtraProps) {
  if (!isMermaid(props.node as HastNode | undefined)) return <CodeBlock {...props} />;
  return (
    <details className="group/code">
      <summary className="w-fit cursor-pointer rounded text-xs text-muted-foreground hover:text-foreground">Código Mermaid</summary>
      <div className="mt-2">
        <CodeBlock {...props} />
      </div>
    </details>
  );
}

const link: Components["a"] = ({ node: _node, ...props }) => <a {...props} target="_blank" rel="noopener noreferrer" />;
const cite: Components["cite"] = ({ node: _node, children, ...props }) => {
  const chunk = (props as Record<string, unknown>)["data-chunk"];
  return typeof chunk === "string" ? <Citation chunk={chunk} /> : <cite>{children}</cite>;
};
const components: Components = { pre: CodeBlock, a: link, cite };
const foldingMermaid: Components = { pre: FoldedMermaid, a: link, cite };

export function RichText({
  text,
  foldMermaid = false,
  className,
}: {
  text: string;
  foldMermaid?: boolean;
  className?: string;
}) {
  return (
    <div className={className ? `prose-chat ${className}` : "prose-chat"}>
      <Markdown
        remarkPlugins={[remarkGfm, remarkCitations]}
        rehypePlugins={[[rehypeSanitize, schema]]}
        components={foldMermaid ? foldingMermaid : components}
      >
        {text}
      </Markdown>
    </div>
  );
}
