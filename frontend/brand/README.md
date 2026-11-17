# Icono de TechDoc Agent

Fuentes del icono. No las sirve la aplicación directamente: de ellas salen los archivos de `src/app/` y el
logo de la cabecera (`src/components/app-logo.tsx`, el mismo dibujo en línea).

| Archivo | Para qué | Sale de él |
|---|---|---|
| `techdoc-agent.png` | El diseño original del autor (512 px, acabado de cristal) | Referencia: el SVG se dibujó midiéndolo |
| `icon.svg` | El mismo dibujo en SVG: misma geometría y degradados que el PNG (error medio de 1–5 niveles de 255 por zona), con fondo transparente y borde nítido en vez del difuminado hacia blanco del PNG | `src/app/icon.svg` (copia exacta: la pestaña del navegador lo dibuja a su resolución), `src/app/favicon.ico` (16, 32 y 48 px, respaldo), `src/app/apple-icon.png` (180 px, a sangre: iOS redondea las esquinas) y `app-logo.tsx` |

En todos los tamaños se usa el dibujo completo, por decisión del autor (las versiones simplificadas para
16 y 32 px se veían peor). El PNG no se sirve tal cual porque no tiene transparencia: su borde se funde con
un blanco opaco que en la pestaña o en la cabecera oscura sería un recuadro.

Para regenerar `favicon.ico`: renderiza `icon.svg` a 256 px (p. ej. con Chromium y Playwright), redúcelo
con Lanczos a 16, 32 y 48 px y júntalos: `convert icon-16.png icon-32.png icon-48.png ../src/app/favicon.ico`.
Si cambias `icon.svg`, copia el archivo también a `src/app/icon.svg`.
