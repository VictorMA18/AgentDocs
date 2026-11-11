import { create } from "zustand";

import type { ProgressEvent, ProviderId, StoredTurn, TurnResult } from "@/lib/api/schemas";

// Estado de la interfaz del chat (Zustand): la conversación en pantalla, lo que se está enviando y
// el progreso en vivo. Lo que vive en el servidor (listas, conversaciones guardadas) va en TanStack Query.

export type ChatMessage =
  | { id: string; role: "user"; text: string }
  | { id: string; role: "agent"; turn: TurnResult }
  | { id: string; role: "error"; text: string };

export type ProgressStep = { tool: string; summary: string; ms: number; error: boolean };
export type Progress = { text: string; steps: ProgressStep[] };

type ChatState = {
  /** Conversación en pantalla; `null` = nueva, aún sin id. */
  sessionId: string | null;
  messages: ChatMessage[];
  /** Progreso del turno en curso; `null` si no hay ninguno. */
  progress: Progress | null;
  busy: boolean;
  /** Proveedor elegido para el próximo turno; `null` = el de por defecto del backend. */
  provider: ProviderId | null;

  reset: () => void;
  load: (sessionId: string, turns: StoredTurn[], provider?: ProviderId | null) => void;
  setProvider: (provider: ProviderId) => void;
  start: (sessionId: string, text: string) => void;
  advance: (sessionId: string, event: ProgressEvent) => void;
  finish: (sessionId: string, turn: TurnResult) => void;
  fail: (sessionId: string, text: string) => void;
};

const newId = () => crypto.randomUUID();

/** Id de conversación: 32 caracteres hexadecimales (el backend acepta [A-Za-z0-9_-]{8,64}). */
export const newSessionId = () => crypto.randomUUID().replaceAll("-", "");

function progressText(event: ProgressEvent, current: string): string {
  if (event.tipo === "en_cola") return "Esperando a que termine otra consulta…";
  if (event.tipo === "pensando") {
    return event.iter === 1 ? "El agente está pensando…" : `Elaborando la respuesta (paso ${event.iter})…`;
  }
  return current;
}

export const useChatStore = create<ChatState>()((set, get) => {
  // Los eventos de un turno solo se aplican si su conversación sigue en pantalla.
  const isCurrent = (sessionId: string) => get().sessionId === sessionId;

  return {
    sessionId: null,
    messages: [],
    progress: null,
    busy: false,
    provider: null,

    reset: () => set({ sessionId: null, messages: [], progress: null, busy: false, provider: null }),

    setProvider: (provider) => set({ provider }),

    load: (sessionId, turns, provider = null) =>
      set({
        sessionId,
        progress: null,
        busy: false,
        provider, // cada conversación sigue con el último proveedor que usó
        messages: turns.flatMap(({ message, ts: _ts, ...turn }): ChatMessage[] => [
          { id: newId(), role: "user", text: message },
          { id: newId(), role: "agent", turn },
        ]),
      }),

    start: (sessionId, text) =>
      set((state) => ({
        sessionId,
        busy: true,
        progress: { text: "El agente está trabajando…", steps: [] },
        messages: [...state.messages, { id: newId(), role: "user", text }],
      })),

    advance: (sessionId, event) => {
      if (!isCurrent(sessionId)) return;
      set((state) => {
        const progress = state.progress ?? { text: "", steps: [] };
        const steps =
          event.tipo === "herramienta"
            ? [...progress.steps, { tool: event.nombre, summary: event.resumen, ms: event.ms, error: event.error }]
            : progress.steps;
        return { progress: { text: progressText(event, progress.text), steps } };
      });
    },

    finish: (sessionId, turn) => {
      if (!isCurrent(sessionId)) return;
      set((state) => ({
        busy: false,
        progress: null,
        messages: [...state.messages, { id: newId(), role: "agent", turn }],
      }));
    },

    fail: (sessionId, text) => {
      if (!isCurrent(sessionId)) return;
      set((state) => ({
        busy: false,
        progress: null,
        messages: [...state.messages, { id: newId(), role: "error", text }],
      }));
    },
  };
});

/** Turnos del agente (para el panel de pasos). Se aplica con useMemo sobre `messages`: un selector
 * que crea un array nuevo en cada lectura haría que Zustand re-renderizara sin fin. */
export const agentTurns = (messages: ChatMessage[]): TurnResult[] =>
  messages.flatMap((m) => (m.role === "agent" ? [m.turn] : []));
