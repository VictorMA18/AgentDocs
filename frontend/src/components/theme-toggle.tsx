"use client";

import { MoonIcon, SunIcon } from "lucide-react";
import { useTheme } from "next-themes";

import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

/** Cambia entre tema claro y oscuro (por defecto sigue al sistema). */
export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const next = resolvedTheme === "dark" ? "light" : "dark";
  const label = next === "dark" ? "Activar modo oscuro" : "Activar modo claro";
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button variant="ghost" size="icon" onClick={() => setTheme(next)} aria-label={label}>
          {/* Los dos iconos se pintan y el CSS elige: evita un desajuste entre servidor y cliente. */}
          <SunIcon className="hidden dark:block" aria-hidden />
          <MoonIcon className="dark:hidden" aria-hidden />
        </Button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}
