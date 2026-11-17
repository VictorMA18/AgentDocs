import { cn } from "cn";
import { useId } from "react";

const DOC = "M308 94H160A36 36 0 0 0 124 130V382.5A36 36 0 0 0 160 418.5H351A36 36 0 0 0 387 382.5V174Z";

/**
 * Logo de la aplicación en línea: el mismo dibujo que `frontend/brand/icon.svg` (recreado a partir de
 * `brand/techdoc-agent.png`), vectorial para que se vea nítido a cualquier tamaño y densidad de pantalla.
 * Decorativo: el título que lo acompaña ya nombra la aplicación. Los degradados llevan ids únicos
 * (useId) para no chocar si el logo aparece más de una vez en la página.
 */
export function AppLogo({ className }: { className?: string }) {
  const id = useId();
  const [bg, edge, paper, ink] = ["bg", "edge", "paper", "ink"].map((name) => `${id}-${name}`);
  return (
    <svg viewBox="0 0 512 512" aria-hidden focusable="false" className={cn("shrink-0", className)}>
      <defs>
        <linearGradient id={bg} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#bcbcbc" />
          <stop offset="0.16" stopColor="#a3a3a3" />
          <stop offset="0.4" stopColor="#7c7c7c" />
          <stop offset="0.64" stopColor="#676767" />
          <stop offset="0.86" stopColor="#838383" />
          <stop offset="1" stopColor="#a2a2a2" />
        </linearGradient>
        <radialGradient id={edge} cx="0.5" cy="0.5" r="0.62">
          <stop offset="0.72" stopColor="#fff" stopOpacity="0" />
          <stop offset="1" stopColor="#fff" stopOpacity="0.28" />
        </radialGradient>
        <radialGradient id={paper} cx="0.5" cy="0.55" r="0.6">
          <stop offset="0" stopColor="#414141" />
          <stop offset="1" stopColor="#636363" />
        </radialGradient>
        <linearGradient id={ink} x1="124" y1="84" x2="400" y2="420" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#ffffff" />
          <stop offset="1" stopColor="#d9d8e7" />
        </linearGradient>
      </defs>
      <rect width="512" height="512" rx="128" fill={`url(#${bg})`} />
      <rect width="512" height="512" rx="128" fill={`url(#${edge})`} />
      <rect x="5" y="5" width="502" height="502" rx="123" fill="none" stroke="#fff" strokeOpacity="0.16" strokeWidth="10" />
      <g transform="translate(1 -10)">
        <path fill={`url(#${paper})`} d={DOC} />
        <g fill="none" stroke={`url(#${ink})`} strokeLinejoin="round" strokeLinecap="round">
          <path strokeWidth="26" d={DOC} />
          <path strokeWidth="26" d="M310.5 96V159A16 16 0 0 0 326.5 175H385" />
          <path strokeWidth="20" d="M164 137.5H229M164 170.5H202" />
          <path
            strokeWidth="14"
            strokeLinecap="butt"
            d="M255.5 235V249M217 293H204.5A11 11 0 0 0 193.5 304V328M294 293H306.5A11 11 0 0 1 317.5 304V328"
          />
        </g>
        <g fill={`url(#${ink})`}>
          <rect x="216" y="188" width="79.5" height="48" rx="10" />
          <rect x="158" y="327" width="71.5" height="50.5" rx="10" />
          <rect x="282" y="327" width="71.5" height="50.5" rx="10" />
          <path d="M255.5 256Q261 287 288.5 292.5Q261 298 255.5 329Q250 298 222.5 292.5Q250 287 255.5 256Z" />
        </g>
      </g>
    </svg>
  );
}
