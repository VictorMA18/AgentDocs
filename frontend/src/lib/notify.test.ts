import { toast } from "sonner";
import { describe, expect, it, vi } from "vitest";

import { notifyError, notifySuccess } from "./notify";

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

describe("notify", () => {
  it("los errores se quedan hasta que se cierran (WCAG 2.2.1); los éxitos usan la duración por defecto", () => {
    notifyError("No se pudo subir");
    notifySuccess("Subido");
    expect(toast.error).toHaveBeenCalledWith("No se pudo subir", { duration: Infinity });
    expect(toast.success).toHaveBeenCalledWith("Subido");
  });
});
