"use client";

import { useSyncExternalStore } from "react";

/**
 * ¿Cumple la ventana esta media query? En el servidor (y en el primer render del cliente) es `false`, así
 * que lo que dependa de ella no debe cambiar el HTML inicial: úsalo para atributos como aria-expanded.
 */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const list = window.matchMedia(query);
      list.addEventListener("change", onChange);
      return () => list.removeEventListener("change", onChange);
    },
    () => window.matchMedia(query).matches,
    () => false,
  );
}
