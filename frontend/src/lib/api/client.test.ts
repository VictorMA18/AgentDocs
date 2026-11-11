import { http, HttpResponse } from "msw/http";
import { describe, expect, it } from "vitest";

import { API, server } from "@/test/server";

import { api, ApiError, OFFLINE_MESSAGE, UNEXPECTED_MESSAGE } from "./client";

describe("api", () => {
  it("valida la respuesta con Zod y aplica valores por defecto", async () => {
    server.use(
      http.get(`${API}/api/conversations/abc12345`, () =>
        HttpResponse.json({
          id: "abc12345", title: "Hola", created: "2026-01-01T00:00:00", updated: "2026-01-01T00:00:00",
          // turno de una transcripción antigua: sin artifacts ni truncated
          turns: [{ message: "hola", reply: "¡Hola!", tool_calls: [], usage: { input_tokens: 1, output_tokens: 1 } }],
        }),
      ),
    );
    const conv = await api.conversation("abc12345");
    expect(conv.turns[0]).toMatchObject({ artifacts: [], truncated: false });
    expect(conv.turns[0].llm).toBeUndefined(); // anterior a la Fase 10: sin proveedor
  });

  it("valida la lista de proveedores y rechaza uno desconocido", async () => {
    const claude = { id: "claude", label: "Claude", model: "m", available: true, reason: null, default: true };
    server.use(http.get(`${API}/api/providers`, () => HttpResponse.json([claude])));
    await expect(api.providers()).resolves.toEqual([claude]);
    server.use(http.get(`${API}/api/providers`, () => HttpResponse.json([{ ...claude, id: "openai" }])));
    await expect(api.providers()).rejects.toThrow(UNEXPECTED_MESSAGE);
  });

  it("rechaza una respuesta con forma inesperada", async () => {
    server.use(http.get(`${API}/api/documents`, () => HttpResponse.json([{ source: 1 }])));
    await expect(api.documents()).rejects.toThrow(UNEXPECTED_MESSAGE);
  });

  it("usa el detail del backend (413, 415…) y el código de estado", async () => {
    server.use(
      http.post(`${API}/api/documents`, () => HttpResponse.json({ detail: "Tipo de archivo no permitido: .exe" }, { status: 415 })),
    );
    const error = await api.uploadDocument(new File(["x"], "a.exe")).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ message: "Tipo de archivo no permitido: .exe", status: 415 });
  });

  it("los 422 de FastAPI (detail en lista) dan un mensaje con el código y qué hacer", async () => {
    server.use(http.get(`${API}/api/documents`, () => HttpResponse.json({ detail: [{ msg: "x" }] }, { status: 422 })));
    await expect(api.documents()).rejects.toThrow("La API respondió con un error (422). Vuelve a intentarlo en unos segundos.");
  });

  it("un fallo de red da un mensaje legible", async () => {
    server.use(http.get(`${API}/healthz`, () => HttpResponse.error()));
    await expect(api.health()).rejects.toThrow(OFFLINE_MESSAGE);
  });

  it("codifica los nombres en la URL", async () => {
    server.use(
      http.delete(`${API}/api/documents/:source`, ({ params }) =>
        HttpResponse.json({ source: params.source, chunks_removed: 2 }),
      ),
    );
    await expect(api.deleteDocument("guía v2.md")).resolves.toEqual({ source: "guía v2.md", chunks_removed: 2 });
    expect(api.artifactUrl("a b.mmd")).toBe(`${API}/api/artifacts/a%20b.mmd`);
  });
});
