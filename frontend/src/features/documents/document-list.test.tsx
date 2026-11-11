import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw/http";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { API, server } from "@/test/server";

import { DocumentList } from "./document-list";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("DocumentList", () => {
  it("lista los documentos y, al quitar uno con confirmación, vuelve a pedir la lista", async () => {
    let docs = [{ source: "taskflow.md", chunks: 8 }, { source: "api.md", chunks: 1 }];
    server.use(
      http.get(`${API}/api/documents`, () => HttpResponse.json(docs)),
      http.get(`${API}/healthz`, () => HttpResponse.json({ status: "ok", documents: docs.length, chunks: 9 })),
      http.delete(`${API}/api/documents/:source`, ({ params }) => {
        docs = docs.filter((d) => d.source !== params.source);
        return HttpResponse.json({ source: params.source, chunks_removed: 8 });
      }),
    );
    render(<DocumentList />, { wrapper });

    expect(await screen.findByText("taskflow.md")).toBeInTheDocument();
    expect(screen.getByText("8 fragmentos")).toBeInTheDocument();
    expect(screen.getByText("1 fragmento")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Quitar taskflow.md" }));
    expect(await screen.findByRole("alertdialog", { name: "¿Quitar «taskflow.md» del índice?" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Quitar documento" }));
    await waitFor(() => expect(screen.queryByText("taskflow.md")).not.toBeInTheDocument());
    expect(screen.getByText("api.md")).toBeInTheDocument();
  });

  it("muestra el estado vacío", async () => {
    server.use(http.get(`${API}/api/documents`, () => HttpResponse.json([])));
    render(<DocumentList />, { wrapper });
    expect(await screen.findByText("Aún no hay documentos indexados.")).toBeInTheDocument();
  });
});
