import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useChatStore } from "@/stores/chat-store";

import { Composer } from "./composer";

beforeEach(() => useChatStore.setState({ sessionId: null, drafts: {} }));

describe("Composer", () => {
  it("lo escrito sobrevive a que el compositor se vuelva a montar y pasa a la conversación que se crea", async () => {
    const { unmount } = render(<Composer onSend={vi.fn()} disabled={false} />);
    await userEvent.type(screen.getByLabelText("Mensaje"), "a medio escribir");
    unmount(); // p. ej. al pasar de / a /c/<id> tras adjuntar el primer documento
    useChatStore.getState().load("conversacion-1", []);
    useChatStore.getState().adoptDraft("conversacion-1");
    render(<Composer onSend={vi.fn()} disabled={false} />);
    expect(screen.getByLabelText("Mensaje")).toHaveValue("a medio escribir");
    act(() => useChatStore.getState().load("conversacion-2", [])); // otra conversación tiene su propio borrador
    expect(screen.getByLabelText("Mensaje")).toHaveValue("");
  });

  it("Enter envía el texto recortado y vacía la caja", async () => {
    const onSend = vi.fn();
    render(<Composer onSend={onSend} disabled={false} />);
    const box = screen.getByLabelText("Mensaje");
    await userEvent.type(box, "  hola  {Enter}");
    expect(onSend).toHaveBeenCalledWith("hola");
    expect(box).toHaveValue("");
  });

  it("Shift+Enter añade una línea sin enviar", async () => {
    const onSend = vi.fn();
    render(<Composer onSend={onSend} disabled={false} />);
    const box = screen.getByLabelText("Mensaje");
    await userEvent.type(box, "a{Shift>}{Enter}{/Shift}b");
    expect(onSend).not.toHaveBeenCalled();
    expect(box).toHaveValue("a\nb");
  });

  it("no envía mensajes vacíos ni mientras hay un turno en curso", async () => {
    const onSend = vi.fn();
    const { rerender } = render(<Composer onSend={onSend} disabled={false} />);
    await userEvent.type(screen.getByLabelText("Mensaje"), "   {Enter}");
    rerender(<Composer onSend={onSend} disabled />);
    await userEvent.type(screen.getByLabelText("Mensaje"), "hola{Enter}");
    expect(onSend).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Enviar" })).toBeDisabled();
  });

  it("limita el mensaje a 8000 caracteres", () => {
    render(<Composer onSend={vi.fn()} disabled={false} />);
    expect(screen.getByLabelText("Mensaje")).toHaveAttribute("maxLength", "8000");
  });

  it("muestra siempre el contador y los controles de la fila inferior", async () => {
    render(<Composer onSend={vi.fn()} disabled={false} footer={<span>selector</span>} />);
    expect(screen.getByTestId("char-count")).toHaveTextContent("0/8000");
    await userEvent.type(screen.getByLabelText("Mensaje"), "hola");
    expect(screen.getByTestId("char-count")).toHaveTextContent("4/8000");
    expect(screen.getByText("selector")).toBeInTheDocument();
  });
});
