import { toast } from "sonner";

// Avisos de la interfaz. Un error no desaparece solo (WCAG 2.2.1): se queda hasta que la persona lo
// cierra, para que dé tiempo a leerlo. Los avisos de éxito sí se van solos.

export const notifyError = (message: string) => toast.error(message, { duration: Infinity });
export const notifySuccess = (message: string) => toast.success(message);
