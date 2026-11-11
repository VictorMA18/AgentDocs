import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ProgressSteps } from "./progress-steps";

describe("ProgressSteps", () => {
  it("muestra el estado y cada herramienta con su etiqueta, resumen y duración", () => {
    render(
      <ProgressSteps
        progress={{
          text: "El agente está pensando…",
          steps: [
            { tool: "buscar_documentos", summary: "tareas", ms: 12, error: false },
            { tool: "herramienta_nueva", summary: "", ms: 3, error: true },
          ],
        }}
      />,
    );
    expect(screen.getByTestId("progress")).toHaveTextContent("El agente está pensando…");
    expect(screen.getByText(/Buscando en la documentación: tareas/)).toHaveTextContent("(12 ms)");
    expect(screen.getByLabelText("Error")).toBeInTheDocument();
    expect(screen.getByText(/herramienta_nueva/)).toBeInTheDocument(); // sin etiqueta: el nombre tal cual
  });
});
