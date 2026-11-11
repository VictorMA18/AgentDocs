"use client";

import { ChevronRightIcon } from "lucide-react";
import { useMemo } from "react";

import { Badge } from "@/components/ui/badge";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import type { ToolCall } from "@/lib/api/schemas";
import { plural, providerLabel } from "@/lib/labels";
import { agentTurns, useChatStore } from "@/stores/chat-store";

function Step({ call }: { call: ToolCall }) {
  return (
    <li className={`rounded-md border p-2 ${call.is_error ? "border-destructive/50" : ""}`}>
      <Collapsible>
        <CollapsibleTrigger className="group flex w-full items-center gap-2 text-left text-sm">
          <ChevronRightIcon className="size-3.5 shrink-0 transition-transform group-data-[state=open]:rotate-90" aria-hidden />
          <span className="font-mono">{call.tool}</span>
          <span className="ml-auto text-xs text-muted-foreground tabular-nums">{call.duration_ms} ms</span>
        </CollapsibleTrigger>
        {call.is_error && (
          <p className="mt-1 text-xs text-destructive">La herramienta devolvió un error; el agente puede corregirlo.</p>
        )}
        <CollapsibleContent>
          <pre className="mt-2 max-h-60 overflow-auto rounded bg-muted p-2 text-xs">
            {JSON.stringify(call.args, null, 2)}
          </pre>
        </CollapsibleContent>
      </Collapsible>
    </li>
  );
}

/** Pasos del agente en cada respuesta de la conversación: herramienta, argumentos, duración y errores. */
export function AgentTrace() {
  const messages = useChatStore((state) => state.messages);
  const turns = useMemo(() => agentTurns(messages), [messages]);

  if (turns.length === 0) {
    return <p className="text-sm text-muted-foreground">Aquí verás las herramientas que usa el agente en cada respuesta.</p>;
  }
  return (
    <ol className="space-y-4" aria-label="Pasos del agente">
      {turns.map((turn, index) => (
        <li key={index} className="space-y-2">
          <div className="flex flex-wrap items-center gap-2 text-sm font-medium">
            Respuesta {index + 1}
            <Badge variant="secondary" className="tabular-nums">
              {turn.usage.input_tokens} / {turn.usage.output_tokens} tokens
            </Badge>
            {turn.llm && <Badge variant="outline">{providerLabel(turn.llm.provider)}</Badge>}
          </div>
          {turn.tool_calls.length === 0 ? (
            <p className="text-xs text-muted-foreground">Respondió sin usar herramientas.</p>
          ) : (
            <ol className="space-y-1.5" aria-label={plural(turn.tool_calls.length, "paso", "pasos")}>
              {turn.tool_calls.map((call, i) => (
                <Step key={i} call={call} />
              ))}
            </ol>
          )}
        </li>
      ))}
    </ol>
  );
}
