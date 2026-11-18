"use client"

import { useTheme } from "next-themes"
import { Toaster as Sonner, type ToasterProps } from "sonner"
import { CircleCheckIcon, InfoIcon, TriangleAlertIcon, OctagonXIcon, Loader2Icon, XIcon } from "lucide-react"

/**
 * Avisos con la superficie del design system (Fase 12.C, ADR-033). Sonner va «sin estilo» y pone solo el
 * apilado, la entrada y la ✕; el aspecto es de globals.css (`.app-toast`): tarjeta (o cristal en Glass),
 * título, detalle en gris y el color semántico solo en el círculo del icono.
 */
const Toaster = ({ toastOptions, ...props }: ToasterProps) => {
  const { theme = "system" } = useTheme()

  return (
    <Sonner
      theme={theme as ToasterProps["theme"]}
      className="toaster group"
      icons={{
        success: <CircleCheckIcon />,
        info: <InfoIcon />,
        warning: <TriangleAlertIcon />,
        error: <OctagonXIcon />,
        loading: <Loader2Icon className="animate-spin" />,
        close: <XIcon />,
      }}
      toastOptions={{
        ...toastOptions, // p. ej. el nombre accesible de la ✕; sin pisar el estilo propio
        unstyled: true,
        classNames: {
          toast: "app-toast",
          icon: "app-toast-icon",
          content: "app-toast-content",
          title: "app-toast-title",
          description: "app-toast-description",
          actionButton: "app-toast-action",
          closeButton: "app-toast-close",
        },
      }}
      {...props}
    />
  )
}

export { Toaster }
