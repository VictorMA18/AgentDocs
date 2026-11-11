import { beforeEach, describe, expect, it } from "vitest";

import { turn } from "@/test/fixtures";

import { agentTurns, newSessionId, useChatStore } from "./chat-store";

const store = () => useChatStore.getState();

beforeEach(() => store().reset());

describe("chat-store", () => {
  it("un turno completo: mensaje, progreso, pasos y respuesta", () => {
    store().start("s1", "hola");
    expect(store()).toMatchObject({ sessionId: "s1", busy: true });
    store().advance("s1", { tipo: "en_cola" });
    expect(store().progress?.text).toBe("Esperando a que termine otra consulta…");
    store().advance("s1", { tipo: "pensando", iter: 2 });
    store().advance("s1", { tipo: "herramienta", nombre: "buscar_documentos", resumen: "x", ms: 5, error: false });
    expect(store().progress).toEqual({
      text: "Elaborando la respuesta (paso 2)…",
      steps: [{ tool: "buscar_documentos", summary: "x", ms: 5, error: false }],
    });
    store().finish("s1", turn);
    expect(store()).toMatchObject({ busy: false, progress: null });
    expect(store().messages.map((m) => m.role)).toEqual(["user", "agent"]);
    expect(agentTurns(store().messages)).toEqual([turn]);
  });

  it("un error termina el turno con un mensaje de error", () => {
    store().start("s1", "hola");
    store().fail("s1", "sin conexión");
    expect(store().messages.at(-1)).toMatchObject({ role: "error", text: "sin conexión" });
    expect(store().busy).toBe(false);
  });

  it("ignora eventos de una conversación que ya no está en pantalla", () => {
    store().start("s1", "hola");
    store().load("s2", []);
    store().advance("s1", { tipo: "pensando", iter: 1 });
    store().finish("s1", turn);
    expect(store()).toMatchObject({ sessionId: "s2", messages: [], progress: null });
  });

  it("carga una conversación guardada como pares pregunta/respuesta", () => {
    store().load("s3", [{ ...turn, message: "¿qué es?", ts: "2026-01-01" }]);
    expect(store().messages).toMatchObject([
      { role: "user", text: "¿qué es?" },
      { role: "agent", turn },
    ]);
  });

  it("los ids de sesión cumplen el patrón del backend", () => {
    expect(newSessionId()).toMatch(/^[A-Za-z0-9_-]{8,64}$/);
  });
});
