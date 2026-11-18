import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw/http";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useChatStore } from "@/stores/chat-store";
import { useUiStore } from "@/stores/ui-store";
import { API, server } from "@/test/server";

import { ArtifactsPanel } from "./artifacts-panel";
import { chatArtifacts } from "./chat-artifacts";

vi.mock("./../chat/mermaid-diagram", () => ({ MermaidDiagram: ({ title }: { title: string }) => <div>diagrama {title}</div> }));

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

const turn = (artifacts: { type: "mermaid" | "requirements"; name: string; title: string }[]) => ({
  reply: "Hecho.",
  tool_calls: [],
  artifacts,
  usage: { input_tokens: 1, output_tokens: 1 },
  truncated: false,
});

beforeEach(() => {
  useUiStore.setState({ selectedArtifact: null });
  useChatStore.getState().load("conversacion-1", [
    { message: "Hazme un diagrama del login", ...turn([{ type: "mermaid", name: "diagrama-login-1a2b.mmd", title: "Flujo de login" }]) },
    { message: "Escribe los requisitos", ...turn([{ type: "requirements", name: "requisitos-3c4d.md", title: "Requisitos de TaskFlow" }]) },
  ]);
});

describe("chatArtifacts", () => {
  it("saca los artefactos de los turnos, del más reciente al más antiguo, con la pregunta que los pidió", () => {
    const items = chatArtifacts(useChatStore.getState().messages);
    expect(items.map((i) => [i.artifact.name, i.question])).toEqual([
      ["requisitos-3c4d.md", "Escribe los requisitos"],
      ["diagrama-login-1a2b.mmd", "Hazme un diagrama del login"],
    ]);
  });
});

describe("ArtifactsPanel (pestaña Artefactos)", () => {
  it("lista los artefactos y abre uno en grande con descarga, copia y vuelta a la lista", async () => {
    server.use(http.get(`${API}/api/artifacts/:name`, () => new HttpResponse("sequenceDiagram\n  A->>B: hola")));
    render(<ArtifactsPanel />, { wrapper });
    const list = screen.getByRole("list", { name: "Artefactos de esta conversación" });
    expect(list).toHaveTextContent("Requisitos de TaskFlow");
    await userEvent.click(screen.getByRole("button", { name: /Flujo de login/ }));
    expect(await screen.findByText("diagrama Flujo de login")).toBeInTheDocument();
    expect(screen.getByText("Pedido con «Hazme un diagrama del login»")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Descargar" })).toHaveAttribute("href", `${API}/api/artifacts/diagrama-login-1a2b.mmd`);
    expect(screen.getByRole("button", { name: "Copiar código" })).toBeEnabled();
    await userEvent.click(screen.getByRole("button", { name: "Todos los artefactos" }));
    expect(screen.getByRole("list", { name: "Artefactos de esta conversación" })).toBeInTheDocument();
  });

  it("sin artefactos explica qué aparecerá aquí", () => {
    useChatStore.getState().load("conversacion-2", []);
    render(<ArtifactsPanel />, { wrapper });
    expect(screen.getByText("Aún no hay artefactos en esta conversación")).toBeInTheDocument();
  });
});
