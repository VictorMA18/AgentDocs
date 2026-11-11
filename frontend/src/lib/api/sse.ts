import { ApiError, errorFromResponse, request } from "./client";
import { streamEventSchema, type ProgressEvent, type TurnResult } from "./schemas";

// El chat usa POST con respuesta en streaming: EventSource solo admite GET, así que se lee el
// cuerpo con un ReadableStream y se separan los eventos SSE a mano.

/** `data:` de un bloque SSE como JSON; `undefined` para comentarios (": keepalive") o JSON roto. */
export function parseSseBlock(block: string): unknown {
  const lines = block.split("\n").filter((line) => line.startsWith("data:"));
  if (lines.length === 0) return undefined;
  const raw = lines.map((line) => line.slice(5).replace(/^ /, "")).join("\n");
  try {
    return JSON.parse(raw);
  } catch {
    return undefined;
  }
}

/** Acumula trozos de texto y emite cada evento completo (los bloques acaban en una línea vacía). */
export function createSseParser(onData: (data: unknown) => void) {
  let buffer = "";
  return (chunk: string) => {
    buffer += chunk.replace(/\r\n?/g, "\n");
    let end: number;
    while ((end = buffer.indexOf("\n\n")) !== -1) {
      const data = parseSseBlock(buffer.slice(0, end));
      buffer = buffer.slice(end + 2);
      if (data !== undefined) onData(data);
    }
  };
}

export type ChatBody = { session_id: string; message: string };

/** Un turno por /api/chat/stream: avisa del progreso y devuelve el evento `final`. */
export async function streamChat(
  body: ChatBody,
  onProgress: (event: ProgressEvent) => void,
  signal?: AbortSignal,
): Promise<TurnResult> {
  const response = await request("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok) throw await errorFromResponse(response);
  if (!response.body) throw new ApiError("El navegador no admite respuestas en streaming.", 0);

  // Un objeto y no dos `let`: TypeScript no sigue las asignaciones hechas dentro del callback.
  const outcome: { result: TurnResult | null; failure: string | null } = { result: null, failure: null };
  const push = createSseParser((data) => {
    const parsed = streamEventSchema.safeParse(data);
    if (!parsed.success) return; // un evento desconocido no rompe el chat
    const event = parsed.data;
    if (event.tipo === "final") {
      const { tipo: _tipo, ...turn } = event;
      outcome.result = turn;
    } else if (event.tipo === "error") outcome.failure = event.detalle;
    else onProgress(event);
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder(); // { stream: true } no corta un carácter UTF-8 partido entre trozos
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    push(decoder.decode(value, { stream: true }));
    if (outcome.failure !== null) throw new ApiError(outcome.failure, response.status);
  }
  if (outcome.result === null) throw new ApiError("La conexión se cerró antes de recibir la respuesta.", 0);
  return outcome.result;
}
