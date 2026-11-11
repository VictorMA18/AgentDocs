"use client";

import { SendHorizontalIcon } from "lucide-react";
import { useState, type FormEvent, type KeyboardEvent } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { MAX_MESSAGE_CHARS, messageSchema } from "@/lib/api/schemas";

type Props = { onSend: (text: string) => void; disabled: boolean };

/** Caja de texto del chat: Enter envía, Shift+Enter añade una línea. Valida con el mismo schema que la API. */
export function Composer({ onSend, disabled }: Props) {
  const [text, setText] = useState("");
  const nearLimit = text.length > MAX_MESSAGE_CHARS * 0.9;

  function submit(event?: FormEvent) {
    event?.preventDefault();
    const parsed = messageSchema.safeParse(text);
    if (disabled || !parsed.success) return;
    setText("");
    onSend(parsed.data);
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <form onSubmit={submit} className="mx-auto flex w-full max-w-3xl items-end gap-2 px-4 pb-4">
      <div className="relative flex-1">
        <label htmlFor="message" className="sr-only">
          Mensaje
        </label>
        <Textarea
          id="message"
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={onKeyDown}
          maxLength={MAX_MESSAGE_CHARS}
          rows={2}
          placeholder="Escribe tu pregunta. Enter envía, Shift+Enter añade una línea."
          className="max-h-48 min-h-14 resize-none pr-16"
        />
        {nearLimit && (
          <span className="absolute right-3 bottom-2 text-xs text-muted-foreground" aria-live="polite">
            {text.length}/{MAX_MESSAGE_CHARS}
          </span>
        )}
      </div>
      <Button type="submit" size="icon-lg" disabled={disabled || !text.trim()} aria-label="Enviar">
        <SendHorizontalIcon aria-hidden />
      </Button>
    </form>
  );
}
