import { toast } from "sonner";
import { describe, expect, it, vi } from "vitest";

import { notifyError, notifySuccess, SUCCESS_MS } from "./notify";

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

describe("notify", () => {
  it("los errores se quedan hasta que se cierran (WCAG 2.2.1) y llevan su detalle", () => {
    notifyError({ title: "No se pudo añadir malo.exe", description: "Tipo de archivo no permitido: .exe" });
    expect(toast.error).toHaveBeenCalledWith("No se pudo añadir malo.exe", {
      description: "Tipo de archivo no permitido: .exe",
      action: undefined,
      duration: Infinity,
    });
  });

  it("los éxitos se van solos y pueden llevar una acción", () => {
    const onClick = vi.fn();
    notifySuccess({ title: "Documento añadido", description: "a.md · 2 fragmentos", action: { label: "Ver documentos", onClick } });
    expect(toast.success).toHaveBeenCalledWith("Documento añadido", {
      description: "a.md · 2 fragmentos",
      action: { label: "Ver documentos", onClick },
      duration: SUCCESS_MS,
    });
  });
});
