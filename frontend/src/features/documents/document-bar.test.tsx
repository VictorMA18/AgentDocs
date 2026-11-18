import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw/http";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TooltipProvider } from "@/components/ui/tooltip";
import { useChatStore } from "@/stores/chat-store";
import { useUiStore } from "@/stores/ui-store";
import { useUploadStore } from "@/stores/upload-store";
import { API, server } from "@/test/server";

import { DocumentBar } from "./document-bar";
import { DocumentsPanel } from "./documents-panel";

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn(), push: vi.fn() }) }));

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={client}>
      <TooltipProvider>{children}</TooltipProvider>
    </QueryClientProvider>
  );
}

const URL = `${API}/api/conversations/conversacion-1/documents`;

beforeEach(() => {
  useChatStore.getState().load("conversacion-1", []);
  useUiStore.setState({ panelTab: "steps", panelSheetOpen: false });
});

describe("DocumentBar (resumen en una línea)", () => {
  it("dice cuántos documentos hay y sus tipos, y abre la pestaña Documentos del panel", async () => {
    server.use(http.get(URL, () => HttpResponse.json([{ source: "taskflow.md", chunks: 8 }, { source: "manual.pdf", chunks: 1 }])));
    render(<DocumentBar conversationId="conversacion-1" busy={false} />, { wrapper });
    const open = await screen.findByRole("button", { name: "Ver los documentos de esta conversación (2)" });
    expect(open).toHaveTextContent("2 documentos");
    expect(open).toHaveTextContent("MD");
    expect(open).toHaveTextContent("PDF"); // el tipo se lee, no solo se ve por color
    await userEvent.click(open);
    expect(useUiStore.getState()).toMatchObject({ panelTab: "documents", panelSheetOpen: true }); // jsdom: pantalla estrecha
  });

  it("sin documentos no ocupa sitio; una subida en curso se anuncia y se ve como «Indexando…»", async () => {
    server.use(http.get(URL, () => HttpResponse.json([])));
    render(<DocumentBar conversationId="conversacion-1" busy={false} />, { wrapper });
    await waitFor(() => expect(screen.queryByRole("button", { name: /Ver los documentos/ })).not.toBeInTheDocument());
    const id = useUploadStore.getState().add("conversacion-1", "notas.md");
    expect(await screen.findByText("Indexando notas.md…")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Indexando notas.md");
    useUploadStore.getState().remove(id);
  });
});

describe("DocumentsPanel (pestaña Documentos)", () => {
  it("lista los documentos con su tipo y quita uno con confirmación", async () => {
    let docs = [{ source: "taskflow.md", chunks: 8 }, { source: "manual.pdf", chunks: 1 }];
    server.use(
      http.get(URL, () => HttpResponse.json(docs)),
      http.delete(`${URL}/:source`, ({ params }) => {
        docs = docs.filter((d) => d.source !== params.source);
        return HttpResponse.json({ source: params.source, chunks_removed: 8 });
      }),
    );
    render(<DocumentsPanel />, { wrapper });
    const list = await screen.findByRole("list", { name: "Documentos de esta conversación" });
    expect(await within(list).findByText("taskflow.md")).toBeInTheDocument();
    expect(within(list).getByText("1 fragmento · ver")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Quitar taskflow.md" }));
    await userEvent.click(await screen.findByRole("button", { name: "Quitar documento" }));
    await waitFor(() => expect(screen.queryByText("taskflow.md")).not.toBeInTheDocument());
  });

  it("sin documentos explica cómo adjuntarlos", async () => {
    server.use(http.get(URL, () => HttpResponse.json([])));
    render(<DocumentsPanel />, { wrapper });
    expect(await screen.findByText("Esta conversación no tiene documentos")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Adjuntar documentos" })).toBeInTheDocument();
  });
});

describe("DocumentView (vista previa)", () => {
  it("al pulsar un documento muestra sus fragmentos en orden y vuelve a la lista", async () => {
    server.use(
      http.get(URL, () => HttpResponse.json([{ source: "taskflow.md", chunks: 2 }])),
      http.get(`${URL}/:source`, () =>
        HttpResponse.json({
          source: "taskflow.md",
          chunks: [
            { id: "taskflow.md#0", n: 0, section: "Instalación", text: "# TaskFlow\n\nSe instala con **pip**." },
            { id: "taskflow.md#1", n: 1, section: "", text: "Segundo fragmento." },
          ],
        }),
      ),
    );
    useUiStore.setState({ selectedDocument: null });
    render(<DocumentsPanel />, { wrapper });
    await userEvent.click(await screen.findByRole("button", { name: "Ver taskflow.md" }));
    const fragments = await screen.findByRole("list", { name: "Fragmentos de taskflow.md" });
    expect(within(fragments).getByText("Fragmento 1 · Instalación")).toBeInTheDocument();
    expect(within(fragments).getByText("pip").tagName).toBe("STRONG"); // Markdown saneado, no texto crudo
    expect(within(fragments).getByText("Fragmento 2")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Todos los documentos" }));
    expect(await screen.findByRole("button", { name: "Ver taskflow.md" })).toBeInTheDocument();
  });
});

