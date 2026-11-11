"use client";

import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { errorMessage } from "@/lib/api/client";
import { useHealth } from "@/lib/api/queries";
import { plural } from "@/lib/labels";

/** Estado de la API (/healthz): conectada con N documentos, o sin conexión. */
export function ApiStatus() {
  const { data, error, isPending } = useHealth();
  if (isPending) return null;
  const ok = !error && data;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge variant={ok ? "outline" : "destructive"} className="gap-1.5" tabIndex={0}>
          <span className={`size-2 rounded-full ${ok ? "bg-success" : "bg-destructive"}`} aria-hidden />
          {ok ? "API conectada" : "API sin conexión"}
        </Badge>
      </TooltipTrigger>
      <TooltipContent>
        {ok
          ? `${plural(data.documents, "documento", "documentos")} · ${plural(data.chunks, "fragmento", "fragmentos")}`
          : errorMessage(error)}
      </TooltipContent>
    </Tooltip>
  );
}
