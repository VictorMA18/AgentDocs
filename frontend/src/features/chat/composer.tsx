"use client";

import { SendHorizontalIcon } from "lucide-react";
import { useEffect, useRef, type FormEvent, type KeyboardEvent, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { MAX_MESSAGE_CHARS, messageSchema } from "@/lib/api/schemas";
import { useChatStore } from "@/stores/chat-store";

type Props = {
  onSend: (text: string) => void;
  disabled: boolean;
  /** Controles de la fila inferior, a la izquierda (el selector de proveedor). */
  footer?: ReactNode;
};

/**
 * Caja de texto del chat: Enter envía, Shift+Enter añade una línea. Valida con el mismo schema que la API.
 *
 * Composición del Frame 14 (ADR-029): texto arriba, botón de enviar redondo a la derecha y una fila
 * inferior con el selector de proveedor a la izquierda y el contador, siempre visible, a la derecha.
 */
export function Composer({ onSend, disabled, footer }: Props) {
  // El borrador vive en el store, por conversación: sobrevive a que la vista se vuelva a montar.
  const text = useChatStore((state) => state.drafts[state.sessionId ?? ""] ?? "");
  const setText = useChatStore((state) => state.setDraft);
  const box = useRef<HTMLTextAreaElement>(null);
  const nearLimit = text.length > MAX_MESSAGE_CHARS * 0.9;
  const dock = useRef<HTMLFormElement>(null);

  // El compositor va pegado abajo sobre los mensajes: la zona que se desplaza reserva su alto como
  // scroll-padding para que un control enfocado con el teclado nunca quede tapado por él (WCAG 2.4.11).
  // Se mide en vivo porque la caja de texto crece al escribir.
  // Si al montarse ya hay borrador (la vista se volvió a montar mientras se escribía) y nada tiene el
  // foco, vuelve a la caja de texto para seguir escribiendo.
  useEffect(() => {
    if (useChatStore.getState().drafts[useChatStore.getState().sessionId ?? ""] && document.activeElement === document.body) {
      box.current?.focus();
    }
  }, []);

  useEffect(() => {
    const form = dock.current;
    const scroller = form?.closest<HTMLElement>("[data-chat-scroll]");
    if (!form || !scroller || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => {
      scroller.style.scrollPaddingBlockEnd = `${form.offsetHeight}px`;
    });
    observer.observe(form);
    return () => observer.disconnect();
  }, []);

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
    <form ref={dock} onSubmit={submit} data-composer-dock className="sticky bottom-0 mx-auto w-full max-w-(--chat-w) px-4 pb-4">
      {/* El foco se marca en todo el compositor (la caja de texto no tiene borde propio). */}
      <div
        data-surface="panel"
        className="relative rounded-xl border bg-card shadow-xs outline-ring has-[textarea:focus-visible]:outline-2 has-[textarea:focus-visible]:outline-offset-2"
      >
        <div className="flex items-start gap-2 p-2">
          <label htmlFor="message" className="sr-only">
            Mensaje
          </label>
          <Textarea
            ref={box}
            id="message"
            value={text}
            onChange={(event) => setText(event.target.value)}
            onKeyDown={onKeyDown}
            maxLength={MAX_MESSAGE_CHARS}
            rows={2}
            placeholder="Escribe tu pregunta. Enter envía, Shift+Enter añade una línea."
            className="max-h-48 min-h-14 flex-1 resize-none border-0 bg-transparent px-2 py-1.5 shadow-none focus-visible:ring-0 dark:bg-transparent"
          />
          <Button type="submit" size="icon-lg" className="shrink-0 rounded-full" disabled={disabled || !text.trim()} aria-label="Enviar">
            <SendHorizontalIcon aria-hidden />
          </Button>
        </div>
        <div className="flex items-center justify-between gap-3 px-3 pb-2">
          <div className="min-w-0 flex-1">{footer}</div>
          {/* Visible siempre; el lector de pantalla solo lo oye cerca del límite (no en cada tecla). */}
          <span className="shrink-0 text-xs text-muted-foreground tabular-nums" aria-hidden data-testid="char-count">
            {text.length}/{MAX_MESSAGE_CHARS}
          </span>
          <span className="sr-only" aria-live="polite">
            {nearLimit ? `${text.length} de ${MAX_MESSAGE_CHARS} caracteres` : ""}
          </span>
        </div>
      </div>
    </form>
  );
}
