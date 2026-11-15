import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeProvider } from "next-themes";
import type { ReactNode } from "react";
import { beforeAll, beforeEach, describe, expect, it } from "vitest";

import { TooltipProvider } from "@/components/ui/tooltip";
import { DEFAULT_APPEARANCE } from "@/lib/appearance";
import { useAppearanceStore } from "@/stores/appearance-store";

import { AppearanceMenu } from "./appearance-menu";

// next-themes consulta el tema del sistema con matchMedia, que jsdom no implementa.
beforeAll(() => {
  window.matchMedia ??= ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  })) as typeof window.matchMedia;
});
beforeEach(() => {
  localStorage.clear();
  document.documentElement.className = "";
  useAppearanceStore.setState(DEFAULT_APPEARANCE);
});

function wrapper({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="light">
      <TooltipProvider>{children}</TooltipProvider>
    </ThemeProvider>
  );
}

async function open() {
  render(<AppearanceMenu />, { wrapper });
  await userEvent.click(screen.getByRole("button", { name: "Apariencia" }));
}

describe("AppearanceMenu", () => {
  it("ofrece estilo, tema y fuente con nombres accesibles", async () => {
    await open();
    for (const group of ["Estilo", "Tema", "Fuente"]) expect(screen.getByRole("radiogroup", { name: group })).toBeInTheDocument();
    for (const name of ["Clásico", "Glass", "Claro", "Oscuro", "Sistema", "En movimiento", "Quieto", "Geist", "DM Sans"]) {
      expect(screen.getByRole("radio", { name })).toBeInTheDocument();
    }
    expect(screen.getByRole("radio", { name: "Clásico" })).toBeChecked();
    expect(screen.getByRole("radio", { name: "Claro" })).toBeChecked();
    expect(screen.getByRole("radio", { name: "Geist" })).toBeChecked();
  });

  it("los grupos no cambian al pasar a Glass (el panel no salta bajo el cursor)", async () => {
    await open();
    const before = screen.getAllByRole("radiogroup").length;
    await userEvent.click(screen.getByRole("radio", { name: "Glass" }));
    expect(document.documentElement.dataset.style).toBe("glass");
    expect(screen.getAllByRole("radiogroup")).toHaveLength(before);
  });

  it("el tema oscuro en Glass es la base negra: conserva el estilo", async () => {
    await open();
    await userEvent.click(screen.getByRole("radio", { name: "Glass" }));
    await userEvent.click(screen.getByRole("radio", { name: "Oscuro" }));
    expect(document.documentElement).toHaveClass("dark");
    expect(document.documentElement.dataset.style).toBe("glass");
  });

  it("Clásico vuelve al estilo Classic sin tocar el tema", async () => {
    useAppearanceStore.getState().setAppearance({ style: "glass" });
    await open();
    await userEvent.click(screen.getByRole("radio", { name: "Oscuro" }));
    await userEvent.click(screen.getByRole("radio", { name: "Clásico" }));
    expect(document.documentElement.dataset.style).toBe("classic");
    expect(document.documentElement).toHaveClass("dark");
  });

  it("el movimiento del fondo solo se elige con Glass y lo guarda", async () => {
    await open();
    expect(screen.getByRole("radiogroup", { name: "Fondo · solo con Glass" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Quieto" })).toBeDisabled();

    await userEvent.click(screen.getByRole("radio", { name: "Glass" }));
    await userEvent.click(screen.getByRole("radio", { name: "Quieto" }));
    expect(document.documentElement.dataset.motion).toBe("off");
  });

  it("«Sistema» deja el tema en manos del sistema operativo", async () => {
    await open();
    await userEvent.click(screen.getByRole("radio", { name: "Oscuro" }));
    await userEvent.click(screen.getByRole("radio", { name: "Sistema" }));
    expect(screen.getByRole("radio", { name: "Sistema" })).toBeChecked();
    expect(localStorage.getItem("theme")).toBe("system");
    expect(document.documentElement).not.toHaveClass("dark"); // el matchMedia de prueba dice «claro»
  });

  it("el color se elige con muestras que tienen nombre y vale con cualquier estilo", async () => {
    await open();
    const group = screen.getByRole("radiogroup", { name: "Color" });
    expect(group).toBeInTheDocument();
    for (const name of ["Neutro", "Rojo", "Azul", "Verde", "Naranja"]) expect(screen.getByRole("radio", { name })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Neutro" })).toBeChecked();

    await userEvent.click(screen.getByRole("radio", { name: "Azul" }));
    expect(document.documentElement.dataset).toMatchObject({ style: "classic", tint: "blue" });
    expect(screen.getByRole("radio", { name: "Azul" })).toBeChecked();
  });

  it("la fuente se elige aparte del estilo", async () => {
    await open();
    await userEvent.click(screen.getByRole("radio", { name: "DM Sans" }));
    expect(document.documentElement.dataset).toMatchObject({ style: "classic", font: "dm-sans" });
  });
});
