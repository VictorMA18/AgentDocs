"use client";

import { useTheme } from "next-themes";
import { useEffect, useId, useState } from "react";

import { Skeleton } from "@/components/ui/skeleton";

type RenderState = { status: "loading" } | { status: "ok"; svg: string } | { status: "error" };

/**
 * Dibuja un diagrama Mermaid en el navegador.
 *
 * `securityLevel: "strict"` hace que Mermaid sanee etiquetas y desactive los clics con JavaScript;
 * solo entonces se inserta su SVG. La librería se carga bajo demanda (pesa) y solo en el cliente.
 */
export function MermaidDiagram({ code }: { code: string }) {
  const { resolvedTheme } = useTheme();
  const reactId = useId();
  const [state, setState] = useState<RenderState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    const id = `mmd-${reactId.replace(/[^a-zA-Z0-9]/g, "")}`;
    (async () => {
      try {
        const { default: mermaid } = await import("mermaid");
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: "strict",
          theme: resolvedTheme === "dark" ? "dark" : "default",
        });
        const { svg } = await mermaid.render(id, code);
        if (!cancelled) setState({ status: "ok", svg });
      } catch {
        // La validación del servidor es heurística: un diagrama puede pasarla y aun así no dibujarse.
        document.getElementById(`d${id}`)?.remove(); // restos del render fallido
        if (!cancelled) setState({ status: "error" });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [code, reactId, resolvedTheme]);

  if (state.status === "loading") return <Skeleton className="h-40 w-full" />;
  if (state.status === "error") {
    return (
      <div className="space-y-2">
        <p className="text-sm text-muted-foreground">Mermaid no pudo dibujar este diagrama. Se muestra su código.</p>
        <pre className="overflow-x-auto rounded-md bg-muted p-3 text-xs">
          <code>{code}</code>
        </pre>
      </div>
    );
  }
  return (
    <div
      className="mermaid-diagram overflow-x-auto [&_svg]:mx-auto [&_svg]:h-auto [&_svg]:max-w-full"
      role="img"
      aria-label="Diagrama"
      // SVG generado por Mermaid en modo estricto (no es texto del modelo sin procesar)
      dangerouslySetInnerHTML={{ __html: state.svg }}
    />
  );
}
