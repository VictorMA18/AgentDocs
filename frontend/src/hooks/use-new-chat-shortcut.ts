"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useChatStore } from "@/stores/chat-store";
import { useUiStore } from "@/stores/ui-store";

/** ¿Es la combinación de «Nueva conversación»? Ctrl+Shift+O (⌘+Shift+O en Mac), como en otros chats. */
export const isNewChatShortcut = (event: Pick<KeyboardEvent, "key" | "ctrlKey" | "metaKey" | "shiftKey" | "altKey">) =>
  (event.ctrlKey || event.metaKey) && event.shiftKey && !event.altKey && event.key.toLowerCase() === "o";

/** Escucha el atajo en toda la página; no hace nada mientras hay un turno en curso. */
export function useNewChatShortcut() {
  const router = useRouter();
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (!isNewChatShortcut(event)) return;
      event.preventDefault();
      if (useChatStore.getState().busy) return;
      useUiStore.getState().setSidebarOpen(false);
      router.push("/");
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [router]);
}

/** Texto del atajo para mostrarlo («Ctrl ⇧ O» o «⌘ ⇧ O»); vacío en el servidor y en el primer render. */
export function useNewChatShortcutLabel(): string {
  const [label, setLabel] = useState("");
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- solo se conoce en el navegador
    setLabel(/Mac|iPhone|iPad/.test(navigator.userAgent) ? "⌘ ⇧ O" : "Ctrl ⇧ O");
  }, []);
  return label;
}
