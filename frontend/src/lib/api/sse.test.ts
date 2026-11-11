import { http, HttpResponse } from "msw/http";
import { describe, expect, it, vi } from "vitest";

import { API, server } from "@/test/server";
import { sseBody, streamResponse, turn } from "@/test/fixtures";

import { createSseParser, parseSseBlock, streamChat } from "./sse";

const body = { session_id: "abcdefgh12", message: "hola" };

describe("parseSseBlock", () => {
  it("lee el JSON de data e ignora comentarios y JSON roto", () => {
    expect(parseSseBlock('event: pensando\ndata: {"tipo":"pensando","iter":1}')).toEqual({ tipo: "pensando", iter: 1 });
    expect(parseSseBlock(": keepalive")).toBeUndefined();
    expect(parseSseBlock("data: {roto")).toBeUndefined();
  });
});

describe("createSseParser", () => {
  it("une eventos partidos entre trozos y acepta saltos CRLF", () => {
    const seen: unknown[] = [];
    const push = createSseParser((data) => seen.push(data));
    push('event: en_cola\r\ndata: {"ti');
    push('po":"en_cola"}\r\n\r\n: keepalive\n\n');
    push('data: {"tipo":"pensando","iter":2}\n');
    expect(seen).toEqual([{ tipo: "en_cola" }]);
    push("\n");
    expect(seen).toEqual([{ tipo: "en_cola" }, { tipo: "pensando", iter: 2 }]);
  });
});

describe("streamChat", () => {
  it("avisa del progreso y devuelve el turno final", async () => {
    server.use(
      http.post(`${API}/api/chat/stream`, async ({ request }) => {
        expect(await request.json()).toEqual(body);
        return streamResponse(
          sseBody([
            { tipo: "pensando", iter: 1 },
            { tipo: "herramienta", nombre: "buscar_documentos", resumen: "tareas", ms: 12, error: false },
            { tipo: "final", ...turn },
          ]),
        );
      }),
    );
    const onProgress = vi.fn();
    await expect(streamChat(body, onProgress)).resolves.toEqual(turn);
    expect(onProgress.mock.calls.map(([event]) => event.tipo)).toEqual(["pensando", "herramienta"]);
  });

  it("lanza el detalle del evento error", async () => {
    server.use(
      http.post(`${API}/api/chat/stream`, () =>
        streamResponse(sseBody([{ tipo: "error", detalle: "El modelo no respondió correctamente." }])),
      ),
    );
    await expect(streamChat(body, vi.fn())).rejects.toThrow("El modelo no respondió correctamente.");
  });

  it("usa el detail de una respuesta HTTP de error", async () => {
    server.use(http.post(`${API}/api/chat/stream`, () => HttpResponse.json({ detail: "Demasiado largo" }, { status: 400 })));
    await expect(streamChat(body, vi.fn())).rejects.toMatchObject({ message: "Demasiado largo", status: 400 });
  });

  it("falla con un mensaje claro si la conexión se corta sin evento final", async () => {
    server.use(http.post(`${API}/api/chat/stream`, () => streamResponse(sseBody([{ tipo: "pensando", iter: 1 }]))));
    await expect(streamChat(body, vi.fn())).rejects.toThrow("La conexión se cerró antes de recibir la respuesta.");
  });

  it("ignora eventos que no cumplen el schema", async () => {
    server.use(
      http.post(`${API}/api/chat/stream`, () =>
        streamResponse(sseBody([{ tipo: "desconocido" }, { tipo: "pensando" }, { tipo: "final", ...turn }])),
      ),
    );
    const onProgress = vi.fn();
    await expect(streamChat(body, onProgress)).resolves.toEqual(turn);
    expect(onProgress).not.toHaveBeenCalled();
  });
});
