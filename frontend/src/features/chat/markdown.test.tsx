import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { RichText } from "./markdown";

describe("RichText", () => {
  it("no ejecuta HTML del modelo: quita scripts, manejadores on* y javascript:", () => {
    const { container } = render(
      <RichText text={'Hola <script>alert(1)</script><img src=x onerror="alert(1)"> [x](javascript:alert(1))'} />,
    );
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("[onerror]")).toBeNull();
    expect(container.querySelector('a[href^="javascript"]')).toBeNull();
  });

  it("los enlaces se abren en otra pestaña sin acceso a la página", () => {
    render(<RichText text="[docs](https://example.com)" />);
    const link = screen.getByRole("link", { name: "docs" });
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("renderiza tablas GFM y copia el código de un bloque", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    render(<RichText text={"| a | b |\n|---|---|\n| 1 | 2 |\n\n```js\nconst x = 1;\n```"} />);
    expect(screen.getByRole("table")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Copiar" }));
    expect(writeText).toHaveBeenCalledWith("const x = 1;\n");
    expect(screen.getByRole("button", { name: "Copiado" })).toBeInTheDocument();
  });
  it("con el diagrama ya dibujado, su código Mermaid se pliega y el resto de código no", () => {
    const text = "Hecho.\n\n```mermaid\nclassDiagram\n  A --> B\n```\n\n```python\nprint(1)\n```";
    const { container } = render(<RichText text={text} foldMermaid />);
    const details = container.querySelector("details")!;
    expect(details).not.toHaveAttribute("open");
    expect(screen.getByText("Código Mermaid").tagName).toBe("SUMMARY");
    expect(details).toHaveTextContent("classDiagram");
    expect(details).not.toHaveTextContent("print(1)");
  });

  it("sin diagrama guardado, el código Mermaid se ve entero", () => {
    const { container } = render(<RichText text={"```mermaid\nflowchart TD\n  A --> B\n```"} />);
    expect(container.querySelector("details")).toBeNull();
    expect(screen.getByText(/flowchart TD/)).toBeVisible();
  });
});
