"use client";

import { MoonIcon, SunIcon } from "lucide-react";
import { useTheme } from "next-themes";

import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

/**
 * Cambia entre tema claro y oscuro (por defecto sigue al sistema).
 *
 * En el servidor el tema aún no se conoce (`resolvedTheme` es `undefined`): nada de lo que se pinta
 * en el HTML inicial puede depender de él o React detecta un desajuste al hidratar. Por eso la
 * etiqueta del botón es fija, los iconos los elige el CSS y el texto que sí depende del tema solo
 * está en el tooltip, que se pinta en el navegador al pasar el ratón.
 */
export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const next = resolvedTheme === "dark" ? "light" : "dark";
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button variant="ghost" size="icon" onClick={() => setTheme(next)} aria-label="Cambiar entre modo claro y oscuro">
          <SunIcon className="hidden dark:block" aria-hidden />
          <MoonIcon className="dark:hidden" aria-hidden />
        </Button>
      </TooltipTrigger>
      <TooltipContent>{next === "dark" ? "Activar modo oscuro" : "Activar modo claro"}</TooltipContent>
    </Tooltip>
  );
}
