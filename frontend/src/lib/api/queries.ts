import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";

// Estado del servidor con TanStack Query: caché, reintentos y estados de carga. Las mutaciones
// invalidan las listas afectadas para que se vuelvan a pedir solas.

export const queryKeys = {
  health: ["health"] as const,
  documents: ["documents"] as const,
  conversations: ["conversations"] as const,
  conversation: (id: string) => ["conversation", id] as const,
  artifact: (name: string) => ["artifact", name] as const,
};

export function useHealth() {
  return useQuery({ queryKey: queryKeys.health, queryFn: api.health, refetchInterval: 30_000, retry: false });
}

export function useDocuments() {
  return useQuery({ queryKey: queryKeys.documents, queryFn: api.documents });
}

export function useUploadDocument() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.uploadDocument,
    onSettled: () => {
      void client.invalidateQueries({ queryKey: queryKeys.documents });
      void client.invalidateQueries({ queryKey: queryKeys.health });
    },
  });
}

export function useDeleteDocument() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.deleteDocument,
    onSettled: () => {
      void client.invalidateQueries({ queryKey: queryKeys.documents });
      void client.invalidateQueries({ queryKey: queryKeys.health });
    },
  });
}

export function useConversations() {
  return useQuery({ queryKey: queryKeys.conversations, queryFn: api.conversations });
}

/** Una conversación guardada. `enabled` evita pedirla cuando ya está en pantalla. */
export function useConversation(id: string, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.conversation(id),
    queryFn: () => api.conversation(id),
    enabled,
    retry: false, // un 404 no mejora reintentando
  });
}

export function useDeleteConversation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.deleteConversation,
    onSettled: (_data, _error, id) => {
      client.removeQueries({ queryKey: queryKeys.conversation(id) });
      void client.invalidateQueries({ queryKey: queryKeys.conversations });
    },
  });
}

/** Contenido de un artefacto: no cambia una vez guardado, así que no caduca. */
export function useArtifactText(name: string) {
  return useQuery({
    queryKey: queryKeys.artifact(name),
    queryFn: () => api.artifactText(name),
    staleTime: Infinity,
    retry: false,
  });
}
