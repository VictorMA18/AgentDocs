import type { TurnResult } from "@/lib/api/schemas";

// Respuestas con la forma exacta del backend (copiadas de una ejecución real de la API).

export const turn: TurnResult = {
  reply: "Según la documentación…\n\n```python\nprint('hola')\n```",
  tool_calls: [{ tool: "buscar_documentos", args: { query: "tareas" }, is_error: false, duration_ms: 12 }],
  artifacts: [],
  usage: { input_tokens: 220, output_tokens: 60 },
  truncated: false,
};

/** Cuerpo SSE como lo emite /api/chat/stream (con un keepalive entre eventos). */
export function sseBody(events: object[]): string {
  return events
    .map((event) => `event: ${(event as { tipo: string }).tipo}\ndata: ${JSON.stringify(event)}\n\n`)
    .join(": keepalive\n\n");
}

/** Respuesta en streaming que entrega el cuerpo en trozos del tamaño indicado (eventos partidos). */
export function streamResponse(body: string, chunkSize = 7, init?: ResponseInit): Response {
  const bytes = new TextEncoder().encode(body);
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (let i = 0; i < bytes.length; i += chunkSize) controller.enqueue(bytes.slice(i, i + chunkSize));
      controller.close();
    },
  });
  return new Response(stream, { headers: { "Content-Type": "text/event-stream" }, ...init });
}
