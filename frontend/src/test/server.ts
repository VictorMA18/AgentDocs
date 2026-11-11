import { setupServer } from "msw/node";

export const API = "http://api.test";

/** Servidor MSW compartido; cada test añade sus handlers con `server.use(...)`. */
export const server = setupServer();
