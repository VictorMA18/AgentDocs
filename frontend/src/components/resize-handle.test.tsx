import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { TooltipProvider } from "@/components/ui/tooltip";
import { DEFAULT_LAYOUT, PANEL_LIMITS } from "@/lib/layout";
import { useLayoutStore } from "@/stores/layout-store";

import { ResizeHandle } from "./resize-handle";

beforeEach(() => {
  localStorage.clear();
  useLayoutStore.setState(DEFAULT_LAYOUT);
});

function renderHandle(edge: "start" | "end" = "end") {
  render(
    <TooltipProvider>
      <ResizeHandle panel="sidebar" controls="sidebar" edge={edge} label="Ancho del lateral" />
    </TooltipProvider>,
  );
  return screen.getByRole("separator", { name: "Ancho del lateral" });
}

describe("ResizeHandle", () => {
  it("expone el ancho como separador accesible", () => {
    const handle = renderHandle();
    expect(handle).toHaveAttribute("aria-orientation", "vertical");
    expect(handle).toHaveAttribute("aria-controls", "sidebar");
    expect(handle).toHaveAttribute("aria-valuenow", "288");
    expect(handle).toHaveAttribute("aria-valuemin", String(PANEL_LIMITS.sidebar.min));
    expect(handle).toHaveAttribute("aria-valuemax", String(PANEL_LIMITS.sidebar.max));
  });

  it("con el teclado: flechas de 16 en 16 px, Inicio y Fin a los límites", async () => {
    const handle = renderHandle();
    handle.focus();
    await userEvent.keyboard("{ArrowRight}");
    expect(handle).toHaveAttribute("aria-valuenow", "304");
    await userEvent.keyboard("{Home}");
    expect(handle).toHaveAttribute("aria-valuenow", String(PANEL_LIMITS.sidebar.min));
    await userEvent.keyboard("{End}");
    expect(handle).toHaveAttribute("aria-valuenow", String(PANEL_LIMITS.sidebar.max));
  });

  it("en el borde izquierdo de un panel, la flecha a la izquierda lo ensancha", async () => {
    const handle = renderHandle("start");
    handle.focus();
    await userEvent.keyboard("{ArrowLeft}");
    expect(handle).toHaveAttribute("aria-valuenow", "304");
  });

  it("arrastrar cambia el ancho y un clic sin arrastrar pasa al tamaño siguiente", () => {
    const handle = renderHandle();
    handle.setPointerCapture = () => {};
    handle.hasPointerCapture = () => false;
    fireEvent.pointerDown(handle, { button: 0, clientX: 300, pointerId: 1 });
    fireEvent.pointerMove(handle, { clientX: 340, pointerId: 1 });
    fireEvent.pointerUp(handle, { clientX: 340, pointerId: 1 });
    expect(handle).toHaveAttribute("aria-valuenow", "328");

    fireEvent.pointerDown(handle, { button: 0, clientX: 340, pointerId: 1 });
    fireEvent.pointerUp(handle, { clientX: 340, pointerId: 1 });
    expect(handle).toHaveAttribute("aria-valuenow", String(PANEL_LIMITS.sidebar.max));
  });
});
