import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw/http";
import type { ReactNode } from "react";
import { beforeAll, beforeEach, describe, expect, it } from "vitest";

import { useChatStore } from "@/stores/chat-store";
import { API, server } from "@/test/server";

import { ProviderSelect } from "./provider-select";

// Radix Select usa APIs de puntero que jsdom no implementa.
beforeAll(() => {
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.releasePointerCapture ??= () => {};
  Element.prototype.scrollIntoView ??= () => {};
});
beforeEach(() => useChatStore.getState().reset());

const providers = [
  { id: "claude", label: "Claude", model: "claude-haiku-5-5", available: true, reason: null, default: true },
  { id: "gemini", label: "Gemini", model: "gemini-3.5-flash-lite", available: false, reason: "Falta GEMINI_API_KEY en backend/.env.", default: false },
];

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("ProviderSelect", () => {
  it("muestra el proveedor por defecto con su modelo y deshabilita el no disponible con su motivo", async () => {
    server.use(http.get(`${API}/api/providers`, () => HttpResponse.json(providers)));
    render(<ProviderSelect disabled={false} />, { wrapper });
    const trigger = await screen.findByRole("combobox", { name: "Modelo" });
    await waitFor(() => expect(trigger).toHaveTextContent("Claude"));
    expect(trigger).toHaveTextContent("claude-haiku-5-5");

    await userEvent.click(trigger);
    const gemini = await screen.findByRole("option", { name: /Gemini/ });
    expect(gemini).toHaveAttribute("aria-disabled", "true");
    expect(gemini).toHaveTextContent("Falta GEMINI_API_KEY");
  });

  it("al elegir otro proveedor lo guarda en el store", async () => {
    server.use(
      http.get(`${API}/api/providers`, () =>
        HttpResponse.json(providers.map((p) => ({ ...p, available: true, reason: null }))),
      ),
    );
    render(<ProviderSelect disabled={false} />, { wrapper });
    await userEvent.click(await screen.findByRole("combobox", { name: "Modelo" }));
    await userEvent.click(await screen.findByRole("option", { name: /Gemini/ }));
    expect(useChatStore.getState().provider).toBe("gemini");
  });

  it("queda bloqueado mientras hay un turno en curso", async () => {
    server.use(http.get(`${API}/api/providers`, () => HttpResponse.json(providers)));
    render(<ProviderSelect disabled />, { wrapper });
    expect(await screen.findByRole("combobox", { name: "Modelo" })).toBeDisabled();
  });
});
