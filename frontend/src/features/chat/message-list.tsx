"use client";

import { AlertTriangleIcon } from "lucide-react";
import { useEffect, useRef } from "react";

import { providerLabel } from "@/lib/labels";
import type { ChatMessage, Progress } from "@/stores/chat-store";

import { ArtifactCard } from "./artifact-card";
import { RichText } from "./markdown";
import { ProgressSteps } from "./progress-steps";

function Message({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <div className="ml-auto max-w-[85%] rounded-2xl rounded-br-sm bg-primary px-4 py-2 whitespace-pre-wrap text-primary-foreground">
        {message.text}
      </div>
    );
  }
  if (message.role === "error") {
    return (
      <div className="flex items-start gap-2 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-2 text-sm text-destructive" role="alert">
        <AlertTriangleIcon className="mt-0.5 size-4 shrink-0" aria-hidden />
        {message.text}
      </div>
    );
  }
  const { turn } = message;
  return (
    <article className="max-w-full" data-testid="agent-message">
      <RichText text={turn.reply} />
      {turn.truncated && (
        <p className="mt-1 text-xs text-muted-foreground">El agente llegó al máximo de pasos; la respuesta puede estar incompleta.</p>
      )}
      {turn.artifacts.map((artifact) => (
        <ArtifactCard key={artifact.name} artifact={artifact} />
      ))}
      {turn.llm && (
        <p className="mt-2 text-xs text-muted-foreground" data-testid="answered-by">
          Respondió {providerLabel(turn.llm.provider)} · <span className="font-mono">{turn.llm.model}</span>
        </p>
      )}
    </article>
  );
}

export function MessageList({ messages, progress }: { messages: ChatMessage[]; progress: Progress | null }) {
  const end = useRef<HTMLDivElement>(null);

  // Al llegar un mensaje o un paso nuevo, se baja hasta el final.
  useEffect(() => {
    end.current?.scrollIntoView?.({ block: "end" });
  }, [messages.length, progress?.steps.length, progress?.text]);

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-5 px-4 py-6">
      {messages.map((message) => (
        <Message key={message.id} message={message} />
      ))}
      {progress && <ProgressSteps progress={progress} />}
      <div ref={end} />
    </div>
  );
}
