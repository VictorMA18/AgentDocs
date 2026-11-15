import { useGSAP } from "@gsap/react";
import gsap from "gsap";

// Animaciones de los momentos clave (Fase 11.B, ADR-030): primera carga, estado vacío y mensajes
// nuevos. Nunca en interacciones frecuentes (teclear, pasar por encima, cambiar de pestaña).
gsap.registerPlugin(useGSAP);

export const REDUCED_MOTION = "(prefers-reduced-motion: reduce)";

/** Valores de una entrada (better-ui: 300 ms, ease-out, 12 px y 4 px de desenfoque; 100 ms de escalón). */
export const ENTER = { duration: 0.3, y: 12, blur: 4, stagger: 0.1 } as const;

/**
 * Desde dónde entra un elemento. Con movimiento reducido solo hay un fundido de opacidad: nada se
 * desplaza ni se desenfoca. Se usa `opacity` y no `autoAlpha` (que pone `visibility: hidden`): el
 * elemento sigue en el árbol de accesibilidad mientras aparece.
 */
export function enterFrom(reduced: boolean): gsap.TweenVars {
  return reduced ? { opacity: 0 } : { opacity: 0, y: ENTER.y, filter: `blur(${ENTER.blur}px)` };
}

export function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && Boolean(window.matchMedia?.(REDUCED_MOTION).matches);
}

/**
 * Hace entrar `targets` con un escalón entre ellos. Al terminar se quitan los estilos en línea: un
 * `filter` o una `opacity` que se quedaran en un antecesor del compositor lo convertirían en
 * «backdrop root» y apagarían su cristal (ADR-029).
 */
export function enter(targets: gsap.TweenTarget, stagger: number = ENTER.stagger) {
  const reduced = prefersReducedMotion();
  // fromTo y no from: en la primera carga el CSS los tiene a opacidad 0 (data-enter), y from() animaría
  // hasta ese 0
  return gsap.fromTo(targets, enterFrom(reduced), {
    ...(reduced ? { opacity: 1 } : { opacity: 1, y: 0, filter: "blur(0px)" }),
    duration: ENTER.duration,
    ease: "power2.out",
    stagger,
    clearProps: "opacity,transform,filter",
  });
}

/** Fin de la entrada de la primera carga: el CSS deja de ocultar los `data-enter-item` (ya los lleva GSAP). */
export function finishFirstEnter() {
  delete document.documentElement.dataset.enter;
}

export { gsap, useGSAP };
