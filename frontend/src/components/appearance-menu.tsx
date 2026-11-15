"use client";

import { cn } from "cn";
import { PaletteIcon } from "lucide-react";
import { useTheme } from "next-themes";
import { RadioGroup } from "radix-ui";
import { useId, useSyncExternalStore } from "react";
import { flushSync } from "react-dom";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { AppFont, AppStyle, BackgroundMotion } from "@/lib/appearance";
import { smoothly, useAppearanceStore } from "@/stores/appearance-store";

type Option<T extends string> = { value: T; label: string; className?: string };

/** Grupo de opciones excluyentes como control segmentado: radios accesibles (flechas para moverse). */
function Segmented<T extends string>({
  label,
  value,
  options,
  onChange,
  disabledReason,
}: {
  label: string;
  value: T;
  options: Option<T>[];
  onChange: (value: T) => void;
  /** Si se da, el grupo se desactiva y el motivo se lee junto a la etiqueta (y forma parte de su nombre). */
  disabledReason?: string;
}) {
  const id = useId();
  return (
    <div className="space-y-1.5">
      <p id={id} className="text-xs font-medium text-muted-foreground">
        {label}
        {disabledReason && (
          <>
            {" "}
            <span className="font-normal">· {disabledReason}</span>
          </>
        )}
      </p>
      <RadioGroup.Root
        aria-labelledby={id}
        disabled={Boolean(disabledReason)}
        value={value}
        onValueChange={(next) => onChange(next as T)}
        orientation="horizontal"
        loop
        className="flex gap-1 rounded-lg bg-muted p-1 data-disabled:opacity-50"
      >
        {options.map((option) => (
          <RadioGroup.Item
            key={option.value}
            value={option.value}
            className={cn(
              "flex-1 rounded-md px-2 py-1.5 text-sm font-medium text-muted-foreground transition-colors outline-none hover:text-foreground data-[state=checked]:hover:text-primary-foreground focus-visible:ring-3 focus-visible:ring-ring/50 data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground data-[state=checked]:shadow-sm",
              option.className,
            )}
          >
            {option.label}
          </RadioGroup.Item>
        ))}
      </RadioGroup.Root>
    </div>
  );
}

type Theme = "light" | "dark" | "system";

const STYLE_OPTIONS: Option<AppStyle>[] = [
  { value: "classic", label: "Clásico" },
  { value: "glass", label: "Glass" },
];
const THEME_OPTIONS: Option<Theme>[] = [
  { value: "light", label: "Claro" },
  { value: "dark", label: "Oscuro" },
  { value: "system", label: "Sistema" },
];
const MOTION_OPTIONS: Option<BackgroundMotion>[] = [
  { value: "on", label: "En movimiento" },
  { value: "off", label: "Quieto" },
];

const REDUCED_MOTION = "(prefers-reduced-motion: reduce)";
/** Si el sistema pide menos movimiento (se sigue en vivo; en el servidor se supone que no). */
function usePrefersReducedMotion() {
  return useSyncExternalStore(
    (notify) => {
      const query = window.matchMedia?.(REDUCED_MOTION);
      query?.addEventListener?.("change", notify);
      return () => query?.removeEventListener?.("change", notify);
    },
    () => Boolean(window.matchMedia?.(REDUCED_MOTION).matches),
    () => false,
  );
}
const FONT_OPTIONS: Option<AppFont>[] = [
  // cada fuente se muestra escrita en sí misma
  { value: "geist", label: "Geist", className: "font-[family-name:var(--font-geist-sans)]" },
  { value: "dm-sans", label: "DM Sans", className: "font-[family-name:var(--font-dm-sans)]" },
];

/**
 * Menú «Apariencia» (ADR-029): estilo (Clásico o Glass), tema (Claro, Oscuro o el del sistema; en
 * Glass es la base blanca o negra del cristal), movimiento del fondo de Glass y fuente. Los grupos
 * están siempre: si uno apareciera según otro, el panel cambiaría de alto y los controles se moverían
 * bajo el cursor; el del fondo se desactiva (con el motivo a la vista) cuando no aplica.
 *
 * Como en el antiguo ThemeToggle, la etiqueta del botón es fija: lo que depende del tema solo se pinta
 * en el navegador, dentro del panel.
 */
export function AppearanceMenu() {
  const { theme: chosen, setTheme } = useTheme();
  const { style, font, motion, setAppearance } = useAppearanceStore();
  const reducedMotion = usePrefersReducedMotion();
  const theme: Theme = chosen === "dark" || chosen === "light" ? chosen : "system";

  function changeTheme(next: Theme) {
    smoothly(() => {
      // next-themes pone la clase en un efecto; aquí se pone ya, para que el fundido capture el tema nuevo
      const dark = next === "dark" || (next === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
      document.documentElement.classList.toggle("dark", dark);
      document.documentElement.style.colorScheme = dark ? "dark" : "light";
      flushSync(() => setTheme(next));
    });
  }

  return (
    <Popover>
      <Tooltip>
        <TooltipTrigger asChild>
          <PopoverTrigger asChild>
            <Button variant="ghost" size="icon" aria-label="Apariencia">
              <PaletteIcon aria-hidden />
            </Button>
          </PopoverTrigger>
        </TooltipTrigger>
        <TooltipContent>Apariencia</TooltipContent>
      </Tooltip>
      <PopoverContent align="end" className="w-72 gap-4 p-3" aria-label="Apariencia">
        <Segmented<AppStyle>
          label="Estilo"
          value={style}
          onChange={(next) => smoothly(() => flushSync(() => setAppearance({ style: next })))}
          options={STYLE_OPTIONS}
        />
        <Segmented<Theme> label="Tema" value={theme} onChange={changeTheme} options={THEME_OPTIONS} />
        <Segmented<BackgroundMotion>
          label="Fondo"
          value={motion}
          onChange={(next) => setAppearance({ motion: next })}
          options={MOTION_OPTIONS}
          disabledReason={style !== "glass" ? "solo con Glass" : reducedMotion ? "tu sistema pide menos movimiento" : undefined}
        />
        <Segmented<AppFont>
          label="Fuente"
          value={font}
          onChange={(next) => smoothly(() => flushSync(() => setAppearance({ font: next })))}
          options={FONT_OPTIONS}
        />
      </PopoverContent>
    </Popover>
  );
}
