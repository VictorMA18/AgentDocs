import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TooltipProvider } from "@/components/ui/tooltip";
import { useChatStore } from "@/stores/chat-store";
import { useUiStore } from "@/stores/ui-store";

import { ConversationPanel } from "./conversation-panel";

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn(), push: vi.fn() }) }));

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={client}>
      <TooltipProvider>{children}</TooltipProvider>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  useChatStore.getState().reset();
  useUiStore.setState({ panelTab: "documents", selectedArtifact: null });
});

describe("ConversationPanel", () => {
  it("tres pestañas que se recorren con las flechas (patrón Tabs de APG) y recuerdan la elegida", async () => {
    render(<ConversationPanel />, { wrapper });
    const documents = screen.getByRole("tab", { name: "Documentos" });
    expect(documents).toHaveAttribute("aria-selected", "true");
    documents.focus();
    await userEvent.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Artefactos" })).toHaveAttribute("aria-selected", "true");
    expect(useUiStore.getState().panelTab).toBe("artifacts");
    await userEvent.keyboard("{ArrowRight}");
    expect(screen.getByRole("tabpanel", { name: "Pasos" })).toHaveTextContent("Aquí verás las herramientas");
  });

  it("openPanel elige la pestaña y el artefacto", () => {
    useUiStore.getState().openPanel("artifacts", "diagrama-x.mmd");
    expect(useUiStore.getState()).toMatchObject({ panelTab: "artifacts", selectedArtifact: "diagrama-x.mmd", panelSheetOpen: true });
  });
});
