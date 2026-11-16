// Sin dependencias de GSAP: lo importa layout.tsx (componente de servidor) para el script previo a pintar.

/**
 * Marca la primera carga como «entrada pendiente» (`data-enter="pending"` en <html>): el CSS oculta los
 * elementos con `data-enter-item` hasta que GSAP los hace entrar (src/lib/motion.ts). Sin esto, el HTML
 * del servidor se vería un instante y luego desaparecería para animarse. Si el JavaScript no llegara a
 * cargar, a los 2,5 s se muestran igualmente.
 */
export function enterScript(): string {
  return `(function(){var r=document.documentElement;r.dataset.enter="pending";setTimeout(function(){delete r.dataset.enter},2500)})()`;
}
