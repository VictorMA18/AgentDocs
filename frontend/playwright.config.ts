import { defineConfig, devices } from "@playwright/test";

// E2E de punta a punta: el backend real (create_app) con un LLM falso guionizado
// (backend/tests/e2e_server.py) y el frontend en modo desarrollo apuntando a él. Se usa `next dev`
// y no la versión compilada porque React solo avisa de los desajustes de hidratación en desarrollo.
// Puertos propios para no chocar con los de desarrollo (8000 y 3000).
const API_PORT = 8001;
const WEB_PORT = 3100;
const WEB_URL = `http://127.0.0.1:${WEB_PORT}`;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false, // un único backend con estado compartido
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: { baseURL: WEB_URL, trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "../.venv/bin/python tests/e2e_server.py",
      cwd: "../backend",
      url: `http://127.0.0.1:${API_PORT}/healthz`,
      env: { E2E_API_PORT: String(API_PORT), E2E_FRONT_ORIGIN: WEB_URL },
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: `pnpm dev --hostname 127.0.0.1 --port ${WEB_PORT}`,
      url: WEB_URL,
      env: { NEXT_PUBLIC_API_URL: `http://127.0.0.1:${API_PORT}`, NEXT_DIST_DIR: ".next-e2e" },
      reuseExistingServer: false,
      timeout: 180_000,
    },
  ],
});
