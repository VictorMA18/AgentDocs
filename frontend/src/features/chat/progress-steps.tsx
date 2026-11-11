import { CheckIcon, Loader2Icon, XIcon } from "lucide-react";

import { toolLabel } from "@/lib/labels";
import type { Progress } from "@/stores/chat-store";

/** Lo que hace el agente mientras trabaja (eventos de /api/chat/stream). Todo entra como texto. */
export function ProgressSteps({ progress }: { progress: Progress }) {
  return (
    <div className="rounded-lg border border-dashed p-3 text-sm" role="status" aria-live="polite">
      <p className="flex items-center gap-2 text-muted-foreground">
        <Loader2Icon className="size-4 animate-spin" aria-hidden />
        {progress.text}
      </p>
      {progress.steps.length > 0 && (
        <ul className="mt-2 space-y-1">
          {progress.steps.map((step, index) => (
            <li key={index} className={`flex items-start gap-2 ${step.error ? "text-destructive" : ""}`}>
              {step.error ? (
                <XIcon className="mt-0.5 size-4 shrink-0" aria-label="Error" />
              ) : (
                <CheckIcon className="mt-0.5 size-4 shrink-0 text-emerald-600 dark:text-emerald-400" aria-label="Hecho" />
              )}
              <span>
                {toolLabel(step.tool)}
                {step.summary && `: ${step.summary}`}
                <span className="text-muted-foreground"> ({step.ms} ms)</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
