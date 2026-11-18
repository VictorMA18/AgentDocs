import { FileTextIcon, WorkflowIcon } from "lucide-react";

import type { Artifact } from "@/lib/api/schemas";

/** Icono del tipo de artefacto (diagrama o requisitos) en un recuadro con el acento. Decorativo. */
export function ArtifactIcon({ type }: { type: Artifact["type"] }) {
  const Icon = type === "mermaid" ? WorkflowIcon : FileTextIcon;
  return (
    <span className="grid size-8 shrink-0 place-items-center rounded-md bg-primary/10 text-primary" aria-hidden>
      <Icon className="size-4" />
    </span>
  );
}
