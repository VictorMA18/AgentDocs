import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw/http";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it } from "vitest";

import { useChatStore } from "@/stores/chat-store";
import { API, server } from "@/test/server";

import { splitCitations } from "./citations";
import { RichText } from "./markdown";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

beforeEach(() => useChatStore.getState().load("conversacion-1", []));

describe("splitCitations", () => {
  it("separa el texto y las citas, también varias seguidas", () => {
    const parts = splitCitations("Hace 3 reintentos [taskflow.md#5][api.md#12].");
    expect(parts.map((p) => (p.type === "text" ? p.value : `<${(p.data?.hProperties as { dataChunk: string }).dataChunk}>`))).toEqual([
      "Hace 3 reintentos ",
      "<taskflow.md#5>",
      "<api.md#12>",
      ".",
    ]);
  });

  it("no toma por cita lo que no lo es", () => {
    for (const text of ["[nota]", "[a b.md#1]", "[x.md#]", "lista[0]", "[../x.md#1]"]) {
      expect(splitCitations(text)).toEqual([{ type: "text", value: text }]);
    }
  });
});

describe("citas en las respuestas", () => {
  it("una cita es un botón que abre el texto del fragmento de esa conversación", async () => {
    let asked = "";
    server.use(
      http.get(`${API}/api/conversations/:id/fragments/:chunk`, ({ params }) => {
        asked = `${String(params.id)} ${String(params.chunk)}`;
        return HttpResponse.json({ id: params.chunk, source: "taskflow.md", text: "max_retries vale 3 por defecto." });
      }),
    );
    render(<RichText text="Por defecto hace 3 reintentos [taskflow.md#5]." />, { wrapper });
    // el id interno empieza en 0; a la persona se le cuenta desde 1
    const cite = screen.getByRole("button", { name: "Ver el fragmento 6 de taskflow.md" });
    expect(cite).toHaveTextContent("MDtaskflow.md· 6");
    await userEvent.click(cite);
    expect(await screen.findByText("max_retries vale 3 por defecto.")).toBeInTheDocument();
    expect(asked).toBe("conversacion-1 taskflow.md#5");
  });

  it("dentro del código y de los enlaces se queda como texto", () => {
    render(<RichText text={"`[a.md#1]` y [b.md#2](https://example.com)"} />, { wrapper });
    expect(screen.queryByRole("button", { name: /Ver el fragmento/ })).not.toBeInTheDocument();
    expect(screen.getByText("[a.md#1]")).toBeInTheDocument();
  });

  it("si el fragmento ya no existe lo dice y explica qué hacer", async () => {
    server.use(
      http.get(`${API}/api/conversations/:id/fragments/:chunk`, () =>
        HttpResponse.json({ detail: "Este fragmento ya no está en los documentos de esta conversación. Vuelve a adjuntar el documento para consultarlo." }, { status: 404 }),
      ),
    );
    render(<RichText text="Ver [viejo.md#1]." />, { wrapper });
    await userEvent.click(screen.getByRole("button", { name: "Ver el fragmento 2 de viejo.md" }));
    expect(await screen.findByText(/Vuelve a adjuntar el documento/)).toBeInTheDocument();
  });
});
