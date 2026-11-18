import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import { http, HttpResponse } from "msw/http";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useChatStore } from "@/stores/chat-store";
import { useUploadStore } from "@/stores/upload-store";
import { API, server } from "@/test/server";

import { useAttachDocuments } from "./use-attach-documents";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace, push: vi.fn() }) }));
const notify = vi.hoisted(() => ({ notifySuccess: vi.fn(), notifyError: vi.fn() }));
vi.mock("@/lib/notify", () => notify);

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

const file = (name: string) => new File(["# T\n\nTexto."], name, { type: "text/markdown" });
// jsdom pierde el nombre del archivo en el FormData («blob»): el servidor falso responde en orden.
let names: string[] = [];

beforeEach(() => {
  replace.mockClear();
  notify.notifySuccess.mockClear();
  notify.notifyError.mockClear();
  useChatStore.getState().reset();
  server.use(
    http.post(`${API}/api/conversations/:id/documents`, () =>
      HttpResponse.json({ source: names.shift(), chunks: 2, warnings: [] }, { status: 201 }),
    ),
    http.get(`${API}/api/conversations/:id/documents`, () => HttpResponse.json([])),
    http.get(`${API}/api/conversations`, () => HttpResponse.json([])),
  );
});

describe("useAttachDocuments", () => {
  it("en un chat nuevo crea la conversación, pasa a /c/<id> al entrar el primero y avisa una vez de todo", async () => {
    names = ["a.md", "b.md"];
    const { result } = renderHook(() => useAttachDocuments(), { wrapper });
    await act(() => result.current([file("a.md"), file("b.md")]));
    const id = useChatStore.getState().sessionId!;
    expect(id).toMatch(/^[0-9a-f]{32}$/);
    expect(replace).toHaveBeenCalledWith(`/c/${id}`);
    expect(notify.notifySuccess).toHaveBeenCalledTimes(1);
    expect(notify.notifySuccess).toHaveBeenCalledWith(
      expect.objectContaining({ title: "2 documentos añadidos", description: "a.md, b.md", action: expect.objectContaining({ label: "Ver documentos" }) }),
    );
    expect(useUploadStore.getState().uploads).toEqual([]);
  });

  it("si no entra ninguno, el chat nuevo sigue siendo nuevo y el error dice qué falló", async () => {
    server.use(
      http.post(`${API}/api/conversations/:id/documents`, () =>
        HttpResponse.json({ detail: "Tipo de archivo no permitido: .exe" }, { status: 415 }),
      ),
    );
    const { result } = renderHook(() => useAttachDocuments(), { wrapper });
    await act(() => result.current([file("malo.exe")]));
    expect(useChatStore.getState().sessionId).toBeNull();
    expect(replace).not.toHaveBeenCalled();
    expect(notify.notifyError).toHaveBeenCalledWith({ title: "No se pudo añadir malo.exe", description: "Tipo de archivo no permitido: .exe" });
  });

  it("en una conversación abierta adjunta ahí, sin cambiar de conversación", async () => {
    useChatStore.getState().load("conversacion-1", []);
    window.history.replaceState(null, "", "/c/conversacion-1");
    names = ["c.md"];
    const { result } = renderHook(() => useAttachDocuments(), { wrapper });
    await act(() => result.current([file("c.md")]));
    expect(useChatStore.getState().sessionId).toBe("conversacion-1");
    expect(replace).not.toHaveBeenCalled();
    expect(notify.notifySuccess).toHaveBeenCalledWith(expect.objectContaining({ title: "Documento añadido", description: "c.md · 2 fragmentos" }));
    window.history.replaceState(null, "", "/");
  });
});
