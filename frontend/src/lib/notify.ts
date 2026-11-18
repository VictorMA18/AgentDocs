import { toast } from "sonner";

// Avisos de la interfaz (Fase 12.C, ADR-033): tarjeta del design system con un título corto, un detalle
// opcional y, cuando tiene sentido, una acción. El aspecto vive en globals.css (`.app-toast`).
// Un error no desaparece solo (WCAG 2.2.1): se queda hasta que la persona lo cierra y su detalle dice
// qué hacer. Los avisos de éxito se van a los 5 s.

export type Notice = {
  /** Qué pasó, en pocas palabras: «Documento añadido». */
  title: string;
  /** El detalle: «taskflow.md · 8 fragmentos», o en un error, el motivo y qué hacer. */
  description?: string;
  action?: { label: string; onClick: () => void };
};

export const SUCCESS_MS = 5_000;

export const notifySuccess = ({ title, description, action }: Notice) =>
  toast.success(title, { description, action, duration: SUCCESS_MS });

export const notifyError = ({ title, description, action }: Notice) =>
  toast.error(title, { description, action, duration: Infinity });
