import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw/http";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { API, server } from "@/test/server";

import { ConversationList } from "./conversation-list";

vi.mock("next/navigation", () => ({ useParams: () => ({}), useRouter: () => ({ push: vi.fn() }) }));

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

const daysAgo = (n: number) => new Date(Date.now() - n * 86_400_000).toISOString();

function serve() {
  let list = [
    { id: "conversacion-1", title: "¿Qué es TaskFlow?", updated: daysAgo(0), turns: 2, provider: "claude" },
    { id: "conversacion-2", title: "Diagrama del login", updated: daysAgo(30), turns: 1, provider: null },
  ];
  const renamed: string[] = [];
  server.use(
    http.get(`${API}/api/conversations`, ({ request }) => {
      const q = new URL(request.url).searchParams.get("q");
      if (!q) return HttpResponse.json(list);
      // como el backend: en el título o, si no, con un fragmento de la respuesta
      if (q === "token") return HttpResponse.json([{ ...list[1], snippet: "…devuelve un token JWT al usuario." }]);
      return HttpResponse.json(list.filter((c) => c.title.toLowerCase().includes(q.toLowerCase())));
    }),
    http.patch(`${API}/api/conversations/:id`, async ({ params, request }) => {
      const { title } = (await request.json()) as { title: string };
      renamed.push(title);
      list = list.map((c) => (c.id === params.id ? { ...c, title } : c));
      return HttpResponse.json({ id: params.id, title });
    }),
  );
  return renamed;
}

describe("ConversationList", () => {
  it("agrupa las conversaciones por fecha", async () => {
    serve();
    render(<ConversationList />, { wrapper });
    const today = await screen.findByRole("list", { name: "Conversaciones de hoy" });
    expect(within(today).getByText("¿Qué es TaskFlow?")).toBeInTheDocument();
    expect(within(screen.getByRole("list", { name: "Conversaciones de anteriores" })).getByText("Diagrama del login")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Hoy" })).toBeInTheDocument();
  });

  it("renombra desde «Más opciones»: Intro guarda y el foco vuelve al botón", async () => {
    const renamed = serve();
    render(<ConversationList />, { wrapper });
    const menu = await screen.findByRole("button", { name: "Más opciones de la conversación ¿Qué es TaskFlow?" });
    await userEvent.click(menu);
    await userEvent.click(await screen.findByRole("menuitem", { name: "Renombrar" }));
    const field = screen.getByRole("textbox", { name: "Nuevo título de la conversación ¿Qué es TaskFlow?" });
    await waitFor(() => expect(field).toHaveFocus());
    await userEvent.clear(field);
    await userEvent.type(field, "Reintentos de TaskFlow{Enter}");
    expect(await screen.findByText("Reintentos de TaskFlow")).toBeInTheDocument();
    expect(renamed).toEqual(["Reintentos de TaskFlow"]);
    await waitFor(() => expect(screen.getByRole("button", { name: /Más opciones de la conversación Reintentos/ })).toHaveFocus());
  });

  it("Esc cancela el renombrado sin pedir nada", async () => {
    const renamed = serve();
    render(<ConversationList />, { wrapper });
    await userEvent.click(await screen.findByRole("button", { name: "Más opciones de la conversación Diagrama del login" }));
    await userEvent.click(await screen.findByRole("menuitem", { name: "Renombrar" }));
    const field = screen.getByRole("textbox", { name: /Nuevo título/ });
    await userEvent.type(field, " cambiado{Escape}");
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(screen.getByText("Diagrama del login")).toBeInTheDocument();
    expect(renamed).toEqual([]);
  });
});

describe("buscador de conversaciones", () => {
  it("filtra en el servidor, resalta lo encontrado y anuncia cuántas hay", async () => {
    serve();
    render(<ConversationList />, { wrapper });
    const search = await screen.findByRole("searchbox", { name: "Buscar conversaciones" });
    await userEvent.type(search, "token");
    expect(await screen.findByText("1 conversación encontrada")).toBeInTheDocument();
    expect(screen.queryByText("¿Qué es TaskFlow?")).not.toBeInTheDocument();
    const mark = screen.getByText("token", { selector: "mark" });
    expect(mark.parentElement).toHaveTextContent("…devuelve un token JWT al usuario.");
  });

  it("sin resultados lo dice, y Esc borra la búsqueda y vuelve a la lista", async () => {
    serve();
    render(<ConversationList />, { wrapper });
    const search = await screen.findByRole("searchbox", { name: "Buscar conversaciones" });
    await userEvent.type(search, "nada");
    expect(await screen.findByText("Ninguna conversación contiene «nada».")).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(search).toHaveValue("");
    expect(await screen.findByText("¿Qué es TaskFlow?")).toBeInTheDocument();
  });
});
