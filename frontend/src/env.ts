import { z } from "zod";

// Variables públicas validadas al arrancar: si la URL está mal escrita, falla aquí y no en cada fetch.
// Next sustituye `process.env.NEXT_PUBLIC_*` en la compilación, por eso se nombra literalmente.
const schema = z.object({
  NEXT_PUBLIC_API_URL: z.url().default("http://127.0.0.1:8000"),
});

const env = schema.parse({ NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || undefined });

export const API_URL = env.NEXT_PUBLIC_API_URL.replace(/\/$/, "");
