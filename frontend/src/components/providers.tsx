"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { useState, type ReactNode } from "react";

import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";

/** Proveedores de toda la app: caché de TanStack Query, tema (claro/oscuro), tooltips y toasts. */
export function Providers({ children }: { children: ReactNode }) {
  // Un QueryClient por montaje (no global): así no se comparte caché entre peticiones en el servidor.
  const [client] = useState(
    () => new QueryClient({ defaultOptions: { queries: { staleTime: 10_000, refetchOnWindowFocus: false } } }),
  );
  return (
    <QueryClientProvider client={client}>
      <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
        <TooltipProvider>
          {children}
          {/* arriba a la derecha, bajo la cabecera (56 px + márgenes): no tapa la barra de documentos */}
          <Toaster
            closeButton
            position="top-right"
            offset={{ top: 72, right: 16 }}
            mobileOffset={{ top: 64, left: 8, right: 8 }}
            containerAriaLabel="Avisos"
            toastOptions={{ closeButtonAriaLabel: "Cerrar aviso" }}
          />
        </TooltipProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
