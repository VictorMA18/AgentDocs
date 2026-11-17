"use client";

import { cn } from "cn";
import { useId, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";

import { COLLAPSE_AT, nextCollapsibleStep, nextPreset, PANEL_LIMITS, RAIL_WIDTH, type PanelId } from "@/lib/layout";
import { useLayoutStore } from "@/stores/layout-store";

const KEY_STEP = 16; // px por pulsación de flecha
const CLICK_SLOP = 3; // px que se toleran antes de considerar que se está arrastrando
const HINT = "Arrastra o usa las flechas para cambiar el ancho; un clic pasa al tamaño siguiente";
const COLLAPSIBLE_HINT = "Arrastra o usa las flechas para cambiar el ancho; Intro o arrastrar del todo lo pliega; un clic pasa al tamaño siguiente";

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
 * - `collapsible` (solo el lateral, Fase 12.A): arrastrarlo por debajo de COLLAPSE_AT lo pliega a un riel
 *   al soltar (mientras tanto el separador lo avisa); Intro lo pliega o lo restaura (patrón de APG); la
 *   flecha que lo estrecha, ya en el mínimo, también lo pliega. Plegado vale RAIL_WIDTH.
 */
export function ResizeHandle({
  panel,
  controls,
  label,
  edge,
  collapsible = false,
  className,
}: {
  panel: PanelId;
  /** id del panel que cambia de ancho (aria-controls). */
  controls: string;
  label: string;
  edge: "start" | "end";
  /** Se puede plegar a un riel (solo el lateral). */
  collapsible?: boolean;
  className?: string;
}) {
  const value = useLayoutStore((state) => state[panel]);
  const collapsed = useLayoutStore((state) => collapsible && state.collapsed);
  const setWidth = useLayoutStore((state) => state.setWidth);
  const setCollapsed = useLayoutStore((state) => state.setCollapsed);
  const drag = useRef<{ x: number; start: number; moved: boolean } | null>(null);
  const [armed, setArmed] = useState(false); // soltar ahora plegaría el lateral (estado para pintar)
  const armedRef = useRef(false); // y ref para leerlo al soltar sin esperar a un render
  const { min, max } = PANEL_LIMITS[panel];
  const sign = edge === "end" ? 1 : -1;
  const hint = useId();
  const now = collapsed ? RAIL_WIDTH : value;

  function arm(on: boolean) {
    armedRef.current = on;
    setArmed(on);
    if (on) document.documentElement.dataset.sidebarArmed = "";
    else delete document.documentElement.dataset.sidebarArmed;
  }

  function onPointerDown(event: PointerEvent<HTMLDivElement>) {
    if (event.button !== 0) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    drag.current = { x: event.clientX, start: now, moved: false };
    document.documentElement.dataset.resizing = ""; // sin transición mientras se arrastra
  }

  function onPointerMove(event: PointerEvent<HTMLDivElement>) {
    const current = drag.current;
    if (!current) return;
    const delta = (event.clientX - current.x) * sign;
    if (!current.moved && Math.abs(delta) < CLICK_SLOP) return;
    current.moved = true;
    const target = current.start + delta;
    if (collapsible && target < COLLAPSE_AT) {
      arm(!useLayoutStore.getState().collapsed); // si ya está plegado, no hay nada que avisar
      return;
    }
    arm(false);
    if (collapsible && useLayoutStore.getState().collapsed) setCollapsed(false);
    setWidth(panel, target);
  }

  function endDrag(event: PointerEvent<HTMLDivElement>) {
    const current = drag.current;
    drag.current = null;
    delete document.documentElement.dataset.resizing;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    return current;
  }

  function onPointerUp(event: PointerEvent<HTMLDivElement>) {
    const current = endDrag(event);
    if (armedRef.current && current) {
      // al desplegarlo vuelve al ancho que tenía antes de arrastrar, no al mínimo por el que pasó
      setWidth(panel, current.start);
      setCollapsed(true);
    }
    arm(false);
    if (!current || current.moved) return;
    if (!collapsible) {
      setWidth(panel, nextPreset(panel, value));
      return;
    }
    const step = nextCollapsibleStep(panel, value, collapsed);
    setWidth(panel, step.width);
    setCollapsed(step.collapsed);
  }

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const steps: Record<string, number> = { ArrowRight: KEY_STEP * sign, ArrowLeft: -KEY_STEP * sign };
    if (collapsible && event.key === "Enter") setCollapsed(!collapsed);
    else if (event.key in steps) {
      const step = steps[event.key];
      if (collapsible && collapsed) {
        if (step > 0) setCollapsed(false); // vuelve al ancho que tenía
      } else if (collapsible && step < 0 && value <= min) setCollapsed(true);
      else setWidth(panel, value + step);
    } else if (event.key === "Home") {
      setCollapsed(false);
      setWidth(panel, min);
    } else if (event.key === "End") {
      setCollapsed(false);
      setWidth(panel, max);
    } else return;
    event.preventDefault();
  }

  return (
    <>
      <div
        role="separator"
        aria-orientation="vertical"
        aria-label={label}
        aria-controls={controls}
        aria-valuenow={now}
        aria-valuetext={collapsed ? "Plegado" : `${now} px`}
        aria-valuemin={collapsible ? RAIL_WIDTH : min}
        aria-valuemax={max}
        aria-describedby={hint}
        title={collapsible ? COLLAPSIBLE_HINT : HINT}
        data-collapse={armed ? "armed" : undefined}
        tabIndex={0}
        data-testid={`resize-${panel}`}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={(event) => {
          endDrag(event);
          arm(false);
        }}
        onKeyDown={onKeyDown}
        className={cn(
          // zona de agarre de 8 px con una línea central que aparece al pasar, enfocar o arrastrar
          "group relative z-10 w-2 shrink-0 cursor-col-resize touch-none outline-none select-none",
          "after:absolute after:inset-y-3 after:left-1/2 after:w-0.5 after:-translate-x-1/2 after:rounded-full after:bg-transparent after:transition-colors",
          "hover:after:bg-ring/60 focus-visible:after:bg-ring active:after:bg-ring",
          // a punto de plegarse: la línea se ensancha y cambia el cursor (el lateral se atenúa, ver globals.css)
          "data-[collapse=armed]:cursor-w-resize data-[collapse=armed]:after:w-1 data-[collapse=armed]:after:bg-primary",
          className,
        )}
      />
      <span id={hint} hidden>
        {collapsible ? COLLAPSIBLE_HINT : HINT}
      </span>
    </>
  );
}
