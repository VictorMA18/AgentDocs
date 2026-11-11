"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export type CopyState = "idle" | "copied" | "failed";

/** Copia texto al portapapeles y recuerda el resultado durante `resetMs` (para el texto del botón). */
export function useCopyToClipboard(resetMs = 1500) {
  const [state, setState] = useState<CopyState>("idle");
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => () => clearTimeout(timer.current), []);

  const copy = useCallback(
    async (text: string) => {
      try {
        await navigator.clipboard.writeText(text);
        setState("copied");
      } catch {
        setState("failed");
      }
      clearTimeout(timer.current);
      timer.current = setTimeout(() => setState("idle"), resetMs);
    },
    [resetMs],
  );

  return { state, copy };
}
