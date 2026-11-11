import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";

import { server } from "./server";

// MSW intercepta las peticiones de red: los tests no saben que la API es falsa. Una petición sin
// handler falla (en MSW 3 la opción se llama onUnhandledFrame).
beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  server.resetHandlers();
  cleanup();
});
afterAll(() => server.close());
