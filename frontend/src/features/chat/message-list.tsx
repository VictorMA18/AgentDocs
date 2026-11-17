"use client";

import { AlertTriangleIcon } from "lucide-react";
import { useEffect, useRef } from "react";

import { ProviderLogo } from "@/components/provider-logo";
import { providerLabel } from "@/lib/labels";
import { enter, useGSAP } from "@/lib/motion";
import type { ChatMessage, Progress } from "@/stores/chat-store";

import { ArtifactCard } from "./artifact-card";
import { RichText } from "./markdown";
import { ProgressSteps } from "./progress-steps";

function Message({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <div data-message-id={message.id} className="ml-auto max-w-[85%] rounded-2xl rounded-br-sm bg-primary px-4 py-2 text-chat whitespace-pre-wrap text-primary-foreground">
        {message.text}
      </div>
    );
  }
  if (message.role === "error") {
    return (
      <div data-message-id={message.id} className="flex items-start gap-2 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-2 text-sm text-destructive" role="alert">
        <AlertTriangleIcon className="mt-0.5 size-4 shrink-0" aria-hidden />
        {message.text}
      </div>
    );
  }
  const { turn } = message;
  return (
    <article data-message-id={message.id} className="max-w-full" data-testid="agent-message">
      <RichText text={turn.reply} foldMermaid={turn.artifacts.some((artifact) => artifact.type === "mermaid")} />
      {turn.truncated && (
        <p className="mt-1 text-xs text-muted-foreground">El agente llegó al máximo de pasos; la respuesta puede estar incompleta.</p>
      )}
      {turn.artifacts.map((artifact) => (
        <ArtifactCard key={artifact.name} artifact={artifact} />
      ))}
      {turn.llm && (
        <p className="mt-2 flex flex-wrap items-center gap-x-1 text-xs text-muted-foreground" data-testid="answered-by">
          Respondió <ProviderLogo provider={turn.llm.provider} className="size-3" /> {providerLabel(turn.llm.provider)} ·{" "}
          <span className="font-mono">{turn.llm.model}</span>
        </p>
      )}
    </article>
  );
}

export function MessageList({ messages, progress }: { messages: ChatMessage[]; progress: Progress | null }) {
  const end = useRef<HTMLDivElement>(null);
  const list = useRef<HTMLDivElement>(null);

  // Los mensajes y el bloque de progreso que llegan mientras la lista está en pantalla entran con GSAP
  // (fundido y 12 px; solo fundido con movimiento reducido). Los que ya estaban al montarla, como los
  // de una conversación guardada, no se animan.
  const known = useRef<Set<string> | null>(null);
  const hadProgress = useRef(false);
  useGSAP(
    () => {
      const ids = messages.map((message) => message.id);
      if (known.current === null) {
        known.current = new Set(ids);
        hadProgress.current = Boolean(progress);
        return;
      }
      const seen = known.current;
      const fresh = new Set(ids.filter((id) => !seen.has(id)));
      fresh.forEach((id) => seen.add(id));
      const targets = Array.from(list.current!.querySelectorAll<HTMLElement>("[data-message-id]")).filter((el) =>
        fresh.has(el.dataset.messageId ?? ""),
      );
      const progressBlock = list.current!.querySelector<HTMLElement>("[data-testid=progress]");
      if (progress && !hadProgress.current && progressBlock) targets.push(progressBlock);
      hadProgress.current = Boolean(progress);
      if (targets.length > 0) enter(targets);
    },
    { dependencies: [messages.length, Boolean(progress)], scope: list },
  );

  // Al llegar un mensaje o un paso nuevo, se baja hasta el final de la zona que se desplaza (no basta
  // con scrollIntoView: el final quedaría detrás del compositor, que va pegado abajo).
  useEffect(() => {
    const scroller = end.current?.closest<HTMLElement>("[data-chat-scroll]");
    if (scroller) scroller.scrollTop = scroller.scrollHeight;
    else end.current?.scrollIntoView?.({ block: "end" });
  }, [messages.length, progress?.steps.length, progress?.text]);

  return (
    <div ref={list} className="mx-auto flex w-full max-w-(--chat-w) flex-col gap-5 px-4 py-6">
      {messages.map((message) => (
        <Message key={message.id} message={message} />
      ))}
      {progress && <ProgressSteps progress={progress} />}
      <div ref={end} />
    </div>
  );
}
