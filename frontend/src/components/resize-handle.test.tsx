import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { TooltipProvider } from "@/components/ui/tooltip";
import { COLLAPSE_AT, DEFAULT_LAYOUT, PANEL_LIMITS, RAIL_WIDTH } from "@/lib/layout";
import { useLayoutStore } from "@/stores/layout-store";

import { ResizeHandle } from "./resize-handle";

beforeEach(() => {
  localStorage.clear();
  useLayoutStore.setState(DEFAULT_LAYOUT);
  document.documentElement.removeAttribute("data-sidebar");
});

function renderHandle(edge: "start" | "end" = "end", collapsible = false) {
  render(
    <TooltipProvider>
      <ResizeHandle panel="sidebar" controls="sidebar" edge={edge} label="Ancho del lateral" collapsible={collapsible} />
    </TooltipProvider>,
  );
  const handle = screen.getByRole("separator", { name: "Ancho del lateral" });
  handle.setPointerCapture = () => {};
  handle.hasPointerCapture = () => false;
  return handle;
}

function drag(handle: HTMLElement, from: number, to: number) {
  fireEvent.pointerDown(handle, { button: 0, clientX: from, pointerId: 1 });
  fireEvent.pointerMove(handle, { clientX: to, pointerId: 1 });
  fireEvent.pointerUp(handle, { clientX: to, pointerId: 1 });
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
    fireEvent.pointerDown(handle, { button: 0, clientX: 300, pointerId: 1 });
    fireEvent.pointerMove(handle, { clientX: 340, pointerId: 1 });
    fireEvent.pointerUp(handle, { clientX: 340, pointerId: 1 });
    expect(handle).toHaveAttribute("aria-valuenow", "328");

    fireEvent.pointerDown(handle, { button: 0, clientX: 340, pointerId: 1 });
    fireEvent.pointerUp(handle, { clientX: 340, pointerId: 1 });
    expect(handle).toHaveAttribute("aria-valuenow", String(PANEL_LIMITS.sidebar.max));
  });
});

describe("ResizeHandle plegable (lateral)", () => {
  it("Intro pliega y restaura el ancho anterior; plegado vale el ancho del riel", async () => {
    const handle = renderHandle("end", true);
    expect(handle).toHaveAttribute("aria-valuemin", String(RAIL_WIDTH));
    handle.focus();
    await userEvent.keyboard("{Enter}");
    expect(handle).toHaveAttribute("aria-valuenow", String(RAIL_WIDTH));
    expect(handle).toHaveAttribute("aria-valuetext", "Plegado");
    expect(document.documentElement.dataset.sidebar).toBe("collapsed");
    await userEvent.keyboard("{Enter}");
    expect(handle).toHaveAttribute("aria-valuenow", "288");
  });

  it("la flecha que lo estrecha, ya en el mínimo, lo pliega; la contraria lo despliega", async () => {
    const handle = renderHandle("end", true);
    handle.focus();
    await userEvent.keyboard("{Home}{ArrowLeft}");
    expect(handle).toHaveAttribute("aria-valuetext", "Plegado");
    await userEvent.keyboard("{ArrowRight}");
    expect(handle).toHaveAttribute("aria-valuenow", String(PANEL_LIMITS.sidebar.min));
  });

  it("arrastrar por debajo del umbral avisa y pliega al soltar; arrastrar el riel lo despliega", () => {
    const handle = renderHandle("end", true);
    fireEvent.pointerDown(handle, { button: 0, clientX: 288, pointerId: 1 });
    fireEvent.pointerMove(handle, { clientX: COLLAPSE_AT - 10, pointerId: 1 });
    expect(handle).toHaveAttribute("data-collapse", "armed");
    expect(handle).toHaveAttribute("aria-valuenow", "288"); // aún no: se pliega al soltar
    fireEvent.pointerUp(handle, { clientX: COLLAPSE_AT - 10, pointerId: 1 });
    expect(handle).toHaveAttribute("aria-valuetext", "Plegado");
    expect(handle).not.toHaveAttribute("data-collapse");
    expect(useLayoutStore.getState().sidebar).toBe(288); // se desplegará al ancho de antes de arrastrar

    drag(handle, RAIL_WIDTH, 300);
    expect(handle).toHaveAttribute("aria-valuenow", "300");
    expect(document.documentElement.dataset.sidebar).toBeUndefined();
  });

  it("un clic en el máximo lo pliega y otro lo devuelve al ancho por defecto", () => {
    const handle = renderHandle("end", true);
    act(() => useLayoutStore.getState().setWidth("sidebar", PANEL_LIMITS.sidebar.max));
    drag(handle, 400, 400);
    expect(handle).toHaveAttribute("aria-valuetext", "Plegado");
    drag(handle, 56, 56);
    expect(handle).toHaveAttribute("aria-valuenow", "288");
  });
});

describe("ResizeHandle que cierra el panel de la conversación", () => {
  function renderPanelHandle() {
    window.innerWidth = 1600; // ventana ancha: el máximo dinámico (deja sitio al chat) no recorta los 384 px
    useLayoutStore.setState({ ...DEFAULT_LAYOUT, panelOpen: true });
    render(
      <TooltipProvider>
        <ResizeHandle panel="trace" controls="conversation-panel" edge="start" label="Ancho del panel" closable />
      </TooltipProvider>,
    );
    const handle = screen.getByRole("separator", { name: "Ancho del panel" });
    handle.setPointerCapture = () => {};
    handle.hasPointerCapture = () => false;
    return handle;
  }

  it("arrastrarlo por debajo del mínimo avisa y lo cierra al soltar, conservando el ancho de antes", () => {
    const handle = renderPanelHandle();
    fireEvent.pointerDown(handle, { button: 0, clientX: 1000, pointerId: 1 });
    fireEvent.pointerMove(handle, { clientX: 1000 + 384, pointerId: 1 }); // borde izquierdo: a la derecha estrecha
    expect(handle).toHaveAttribute("data-collapse", "armed");
    fireEvent.pointerUp(handle, { clientX: 1000 + 384, pointerId: 1 });
    expect(useLayoutStore.getState()).toMatchObject({ panelOpen: false, trace: 384 });
  });

  it("Intro lo cierra, y la flecha que lo estrecha ya en el mínimo también", async () => {
    const handle = renderPanelHandle();
    handle.focus();
    await userEvent.keyboard("{Enter}");
    expect(useLayoutStore.getState().panelOpen).toBe(false);
    act(() => useLayoutStore.setState({ panelOpen: true, trace: PANEL_LIMITS.trace.min }));
    handle.focus();
    await userEvent.keyboard("{ArrowRight}");
    expect(useLayoutStore.getState().panelOpen).toBe(false);
  });
});

