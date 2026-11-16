"use client";

import { cn } from "cn";
import { useId, useRef, type KeyboardEvent, type PointerEvent } from "react";

import { nextPreset, PANEL_LIMITS, type PanelId } from "@/lib/layout";
import { useLayoutStore } from "@/stores/layout-store";

const KEY_STEP = 16; // px por pulsación de flecha
const CLICK_SLOP = 3; // px que se toleran antes de considerar que se está arrastrando
const HINT = "Arrastra o usa las flechas para cambiar el ancho; un clic pasa al tamaño siguiente";

/**
 * Separador para cambiar el ancho de un panel (patrón «Window Splitter» de ARIA APG).
 *
 * - Ratón o táctil: se arrastra. Un clic sin arrastrar pasa al tamaño siguiente (mínimo, por defecto,
 *   máximo): es la alternativa sin arrastre que pide WCAG 2.5.7.
 * - Teclado: es enfocable; las flechas cambian el ancho de 16 en 16 px, Inicio y Fin van al mínimo y
 *   al máximo.
 * - Sin tooltip: aparecería junto al cursor y taparía la zona de agarre. La ayuda va en `title` (ratón)
 *   y en una descripción oculta (lector de pantalla).
 * - `edge` es el borde del panel donde está: "end" (a su derecha, arrastrar a la derecha lo ensancha)
 *   o "start" (a su izquierda, como el panel de pasos, que se abre desde la derecha).
 */
export function ResizeHandle({
  panel,
  controls,
  label,
  edge,
  className,
}: {
  panel: PanelId;
  /** id del panel que cambia de ancho (aria-controls). */
  controls: string;
  label: string;
  edge: "start" | "end";
  className?: string;
}) {
  const value = useLayoutStore((state) => state[panel]);
  const setWidth = useLayoutStore((state) => state.setWidth);
  const drag = useRef<{ x: number; start: number; moved: boolean } | null>(null);
  const { min, max } = PANEL_LIMITS[panel];
  const sign = edge === "end" ? 1 : -1;
  const hint = useId();

  function onPointerDown(event: PointerEvent<HTMLDivElement>) {
    if (event.button !== 0) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    drag.current = { x: event.clientX, start: value, moved: false };
  }

  function onPointerMove(event: PointerEvent<HTMLDivElement>) {
    const current = drag.current;
    if (!current) return;
    const delta = (event.clientX - current.x) * sign;
    if (!current.moved && Math.abs(delta) < CLICK_SLOP) return;
    current.moved = true;
    setWidth(panel, current.start + delta);
  }

  function onPointerUp(event: PointerEvent<HTMLDivElement>) {
    const current = drag.current;
    drag.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    if (current && !current.moved) setWidth(panel, nextPreset(panel, value));
  }

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const steps: Record<string, number> = { ArrowRight: KEY_STEP * sign, ArrowLeft: -KEY_STEP * sign };
    if (event.key in steps) setWidth(panel, value + steps[event.key]);
    else if (event.key === "Home") setWidth(panel, min);
    else if (event.key === "End") setWidth(panel, max);
    else return;
    event.preventDefault();
  }

  return (
    <>
        <div
          role="separator"
          aria-orientation="vertical"
          aria-label={label}
          aria-controls={controls}
          aria-valuenow={value}
          aria-valuemin={min}
          aria-valuemax={max}
          aria-describedby={hint}
          title={HINT}
          tabIndex={0}
          data-testid={`resize-${panel}`}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={() => (drag.current = null)}
          onKeyDown={onKeyDown}
          className={cn(
            // zona de agarre de 8 px con una línea central que aparece al pasar, enfocar o arrastrar
            "group relative z-10 w-2 shrink-0 cursor-col-resize touch-none outline-none select-none",
            "after:absolute after:inset-y-3 after:left-1/2 after:w-0.5 after:-translate-x-1/2 after:rounded-full after:bg-transparent after:transition-colors",
            "hover:after:bg-ring/60 focus-visible:after:bg-ring active:after:bg-ring",
            className,
          )}
        />
      <span id={hint} hidden>
        {HINT}
      </span>
    </>
  );
}
