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
          <Toaster
            richColors
            closeButton
            position="top-center"
            containerAriaLabel="Avisos"
            toastOptions={{ closeButtonAriaLabel: "Cerrar aviso" }}
          />
        </TooltipProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
