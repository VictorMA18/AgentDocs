"use client";

import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { errorMessage } from "@/lib/api/client";
import { useHealth } from "@/lib/api/queries";

/**
 * Estado de la API (/healthz): conectada o sin conexión, y por qué. No muestra los documentos que cuenta
 * /healthz: son los del índice global (consola, MCP), no los de las conversaciones de la web (ADR-032).
 */
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
        {ok ? "El servidor del agente responde." : errorMessage(error)}
      </TooltipContent>
    </Tooltip>
  );
}
