import type { Metadata } from "next";
import { DM_Sans, Geist, Geist_Mono } from "next/font/google";

import { AppShell } from "@/components/app-shell";
import { Providers } from "@/components/providers";
import { appearanceScript } from "@/lib/appearance";

import "./globals.css";

// next/font descarga las fuentes al compilar y las sirve desde el propio origen (sin CDN en ejecución).
const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });
// Segunda fuente de texto (la del Frame 14). Las dos se cargan y el usuario elige en «Apariencia».
const dmSans = DM_Sans({ variable: "--font-dm-sans", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "TechDoc Agent",
  description: "Agente que responde sobre tu documentación técnica y genera diagramas y requisitos.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // suppressHydrationWarning: next-themes (clase del tema) y el script de apariencia (data-style,
    // data-tint, data-font) cambian <html> antes de hidratar
    <html
      lang="es"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} ${dmSans.variable} antialiased`}
    >
      <body>
        {/* Antes que nada: pone la apariencia guardada para que no parpadee el estilo por defecto. */}
        <script suppressHydrationWarning dangerouslySetInnerHTML={{ __html: appearanceScript() }} />
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
