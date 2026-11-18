import { create } from "zustand";
import { useShallow } from "zustand/react/shallow";

/**
 * Documentos que se están subiendo e indexando, por conversación. Es global (no estado de un
 * componente) porque adjuntar en un chat nuevo cambia de `/` a `/c/<id>` y la vista se vuelve a montar:
 * el chip «Indexando…» tiene que seguir a la vista en la página nueva.
 */
type Upload = { id: number; conversationId: string; name: string };

type UploadState = {
  uploads: Upload[];
  add: (conversationId: string, name: string) => number;
  remove: (id: number) => void;
};

let next = 0;

export const useUploadStore = create<UploadState>()((set) => ({
  uploads: [],
  add: (conversationId, name) => {
    const id = ++next;
    set((state) => ({ uploads: [...state.uploads, { id, conversationId, name }] }));
    return id;
  },
  remove: (id) => set((state) => ({ uploads: state.uploads.filter((u) => u.id !== id) })),
}));

/**
 * Subidas en curso de una conversación. `useShallow`: el filtro crea un array nuevo en cada lectura y,
 * sin comparar su contenido, Zustand volvería a pintar sin fin.
 */
export function useUploadsFor(conversationId: string | null) {
  return useUploadStore(useShallow((state) => state.uploads.filter((u) => u.conversationId === conversationId)));
}
