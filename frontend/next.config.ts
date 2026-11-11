import type { NextConfig } from "next";

// La única API con la que habla el navegador. Se repite el valor por defecto de src/env.ts porque
// este archivo se evalúa fuera de la app (no puede importar módulos de src/).
const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const isDev = process.env.NODE_ENV !== "production";

// CSP: todo se sirve desde el propio origen (sin CDN) y la única conexión externa es la API.
// 'unsafe-inline' en scripts lo exige el arranque de Next sin nonces; la defensa principal contra
// XSS es no insertar nunca HTML del modelo (Markdown saneado y Mermaid en modo estricto).
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'", // Mermaid y next-themes insertan estilos
  "img-src 'self' data: blob:",
  "font-src 'self'",
  `connect-src 'self' ${API_URL}${isDev ? " ws:" : ""}`,
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const nextConfig: NextConfig = {
  // Las pruebas E2E compilan en otra carpeta para no pisar la del desarrollo.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  poweredByHeader: false,
  // `next dev` escribiría su propio AGENTS.md aquí; las reglas del proyecto están en el AGENTS.md de la raíz.
  agentRules: false,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "no-referrer" },
        ],
      },
    ];
  },
};

export default nextConfig;
