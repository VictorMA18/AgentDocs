import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import { http } from "msw/http";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { sseBody, streamResponse, turn } from "@/test/fixtures";
import { API, server } from "@/test/server";
import { useChatStore } from "@/stores/chat-store";

import { useChatStream } from "./use-chat-stream";

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }) }));

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>;
}

beforeEach(() => useChatStore.getState().reset());

describe("useChatStream", () => {
  async function sendAndCapture(): Promise<Record<string, unknown>> {
    let body: Record<string, unknown> = {};
    server.use(
      http.post(`${API}/api/chat/stream`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return streamResponse(sseBody([{ tipo: "final", ...turn, llm: { provider: "gemini", model: "g" } }]));
      }),
    );
    const { result } = renderHook(() => useChatStream(), { wrapper });
    await act(() => result.current.send("hola"));
    return body;
  }

  it("envía el proveedor elegido", async () => {
    useChatStore.getState().setProvider("gemini");
    expect(await sendAndCapture()).toMatchObject({ message: "hola", provider: "gemini" });
    expect(useChatStore.getState().messages.at(-1)).toMatchObject({ role: "agent", turn: { llm: { provider: "gemini" } } });
  });

  it("sin elección no envía proveedor (el backend usa el de la conversación o el de por defecto)", async () => {
    expect(await sendAndCapture()).not.toHaveProperty("provider");
  });
});
