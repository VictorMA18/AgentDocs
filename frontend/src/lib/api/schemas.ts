import { z } from "zod";

// Forma de cada respuesta de la API (backend/src/techdoc_agent/api/routers/). Se valida en el borde:
// si el backend cambia, el error sale aquí con un mensaje claro y no como un `undefined` en la vista.

export const MAX_MESSAGE_CHARS = 8000; // igual que api/schemas.py

/** Lo que el usuario escribe, con las mismas reglas que ChatRequest en el backend. */
export const messageSchema = z
  .string()
  .trim()
  .min(1, "Escribe un mensaje.")
  .max(MAX_MESSAGE_CHARS, `Máximo ${MAX_MESSAGE_CHARS} caracteres.`);

/** Proveedores del LLM que se pueden elegir (Fase 10, ADR-028). */
export const providerIdSchema = z.enum(["claude", "gemini"]);

export const providerSchema = z.object({
  id: providerIdSchema,
  label: z.string(),
  model: z.string(),
  available: z.boolean(),
  reason: z.string().nullable(),
  default: z.boolean(),
});
export const providerListSchema = z.array(providerSchema);

/** Quién respondió un turno. Las transcripciones anteriores a la Fase 10 no lo tienen. */
export const llmSchema = z.object({ provider: providerIdSchema, model: z.string() });

export const toolCallSchema = z.object({
  tool: z.string(),
  args: z.unknown(),
  is_error: z.boolean(),
  duration_ms: z.number(),
});

export const artifactSchema = z.object({
  name: z.string(),
  type: z.enum(["mermaid", "requirements"]),
  title: z.string().default(""),
});

export const usageSchema = z.object({
  input_tokens: z.number(),
  output_tokens: z.number(),
});

/** Un turno del agente: respuesta de /api/chat y del evento `final` del stream. */
export const turnResultSchema = z.object({
  reply: z.string(),
  tool_calls: z.array(toolCallSchema).default([]),
  artifacts: z.array(artifactSchema).default([]), // las transcripciones antiguas no lo tienen
  usage: usageSchema.default({ input_tokens: 0, output_tokens: 0 }),
  truncated: z.boolean().default(false),
  llm: llmSchema.optional(),
});

export const documentSchema = z.object({ source: z.string(), chunks: z.number() });
export const documentListSchema = z.array(documentSchema);

export const uploadResultSchema = z.object({
  source: z.string(),
  chunks: z.number(),
  warnings: z.array(z.string()).default([]),
});

export const deletedDocumentSchema = z.object({ source: z.string(), chunks_removed: z.number() });

export const conversationSummarySchema = z.object({
  id: z.string(),
  title: z.string(),
  updated: z.string(),
  turns: z.number(),
  provider: providerIdSchema.nullable().optional(), // el del último turno
});
export const conversationListSchema = z.array(conversationSummarySchema);

export const storedTurnSchema = turnResultSchema.extend({
  message: z.string(),
  ts: z.string().optional(),
});

export const conversationSchema = z.object({
  id: z.string(),
  title: z.string(),
  created: z.string(),
  updated: z.string(),
  turns: z.array(storedTurnSchema),
  provider: providerIdSchema.nullable().optional(),
});

export const deletedConversationSchema = z.object({ id: z.string() });

export const healthSchema = z.object({
  status: z.literal("ok"),
  documents: z.number(),
  chunks: z.number(),
});

/** Eventos de /api/chat/stream (campo `tipo`). */
export const streamEventSchema = z.discriminatedUnion("tipo", [
  z.object({ tipo: z.literal("en_cola") }),
  z.object({ tipo: z.literal("pensando"), iter: z.number() }),
  z.object({
    tipo: z.literal("herramienta"),
    nombre: z.string(),
    resumen: z.string().default(""),
    ms: z.number(),
    error: z.boolean(),
  }),
  turnResultSchema.extend({ tipo: z.literal("final") }),
  z.object({ tipo: z.literal("error"), detalle: z.string() }),
]);

export type ProviderId = z.infer<typeof providerIdSchema>;
export type Provider = z.infer<typeof providerSchema>;
export type ToolCall = z.infer<typeof toolCallSchema>;
export type Artifact = z.infer<typeof artifactSchema>;
export type TurnResult = z.infer<typeof turnResultSchema>;
export type DocumentInfo = z.infer<typeof documentSchema>;
export type UploadResult = z.infer<typeof uploadResultSchema>;
export type ConversationSummary = z.infer<typeof conversationSummarySchema>;
export type Conversation = z.infer<typeof conversationSchema>;
export type StoredTurn = z.infer<typeof storedTurnSchema>;
export type Health = z.infer<typeof healthSchema>;
export type StreamEvent = z.infer<typeof streamEventSchema>;
/** Eventos de progreso: todo lo que no cierra el turno. */
export type ProgressEvent = Extract<StreamEvent, { tipo: "en_cola" | "pensando" | "herramienta" }>;
