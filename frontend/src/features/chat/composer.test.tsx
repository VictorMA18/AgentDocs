import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Composer } from "./composer";

describe("Composer", () => {
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
});
