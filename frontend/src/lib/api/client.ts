import type { z } from "zod";

import { API_URL } from "@/env";

import {
  conversationListSchema,
  conversationSchema,
  deletedConversationSchema,
  deletedDocumentSchema,
  documentListSchema,
  healthSchema,
  providerListSchema,
  uploadResultSchema,
} from "./schemas";

/** Error de la API con un mensaje que se puede mostrar tal cual (el `detail` del backend). */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export const OFFLINE_MESSAGE =
  "No se pudo conectar con la API. Comprueba que el backend está arrancado y vuelve a intentarlo.";

export const UNEXPECTED_MESSAGE =
  "La API devolvió datos con un formato inesperado. Comprueba que backend y frontend son de la misma versión.";

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Algo falló en la página. Recárgala y vuelve a intentarlo.";
}

/** `fetch` que convierte el fallo de red en un ApiError legible. */
export async function request(path: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(API_URL + path, init);
  } catch {
    throw new ApiError(OFFLINE_MESSAGE, 0);
  }
}

/** Error de una respuesta no OK: usa `detail` si es texto (los 422 de FastAPI traen una lista). */
export async function errorFromResponse(response: Response): Promise<ApiError> {
  let detail = `La API respondió con un error (${response.status}). Vuelve a intentarlo en unos segundos.`;
  try {
    const body: unknown = await response.json();
    if (body && typeof body === "object" && "detail" in body && typeof body.detail === "string") {
      detail = body.detail;
    }
  } catch {
    // respuesta sin JSON
  }
  return new ApiError(detail, response.status);
}

async function getJson<T>(path: string, schema: z.ZodType<T>, init?: RequestInit): Promise<T> {
  const response = await request(path, init);
  if (!response.ok) throw await errorFromResponse(response);
  const parsed = schema.safeParse(await response.json().catch(() => undefined));
  if (!parsed.success) throw new ApiError(UNEXPECTED_MESSAGE, response.status);
  return parsed.data;
}

const enc = encodeURIComponent;

export const api = {
  health: () => getJson("/healthz", healthSchema),
  providers: () => getJson("/api/providers", providerListSchema),

  documents: () => getJson("/api/documents", documentListSchema),
  uploadDocument: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return getJson("/api/documents", uploadResultSchema, { method: "POST", body });
  },
  deleteDocument: (source: string) =>
    getJson(`/api/documents/${enc(source)}`, deletedDocumentSchema, { method: "DELETE" }),

  conversations: () => getJson("/api/conversations", conversationListSchema),
  conversation: (id: string) => getJson(`/api/conversations/${enc(id)}`, conversationSchema),
  deleteConversation: (id: string) =>
    getJson(`/api/conversations/${enc(id)}`, deletedConversationSchema, { method: "DELETE" }),

  artifactUrl: (name: string) => `${API_URL}/api/artifacts/${enc(name)}`,
  artifactText: async (name: string) => {
    const response = await request(`/api/artifacts/${enc(name)}`);
    if (response.status === 404) throw new ApiError("El archivo de este artefacto ya no existe. Pide al agente que lo genere de nuevo.", 404);
    if (!response.ok) throw await errorFromResponse(response);
    return response.text();
  },
};
