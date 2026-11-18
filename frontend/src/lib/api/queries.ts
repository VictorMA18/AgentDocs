import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";

// Estado del servidor con TanStack Query: caché, reintentos y estados de carga. Las mutaciones
// invalidan las listas afectadas para que se vuelvan a pedir solas.

export const queryKeys = {
  health: ["health"] as const,
  providers: ["providers"] as const,
  documents: ["documents"] as const,
  fragment: (conversationId: string, chunkId: string) => ["fragment", conversationId, chunkId] as const,
  conversations: ["conversations"] as const,
  conversation: (id: string) => ["conversation", id] as const,
  artifact: (name: string) => ["artifact", name] as const,
};

export function useHealth() {
  return useQuery({ queryKey: queryKeys.health, queryFn: api.health, refetchInterval: 30_000, retry: false });
}

/** Proveedores del LLM y si se pueden usar (cambia poco: se refresca cada minuto). */
export function useProviders() {
  return useQuery({ queryKey: queryKeys.providers, queryFn: api.providers, staleTime: 60_000 });
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

/**
 * Conversaciones guardadas, o las que contienen `query`. Cada búsqueda tiene su clave bajo
 * `["conversations"]`, así invalidar la lista invalida también las búsquedas. Mientras llega una
 * búsqueda nueva se siguen viendo los resultados anteriores (no parpadea a «cargando»).
 */
export function useConversations(query = "") {
  return useQuery({
    queryKey: query ? [...queryKeys.conversations, query] : queryKeys.conversations,
    queryFn: () => api.conversations(query),
    placeholderData: keepPreviousData,
  });
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

/** Renombra una conversación: cambia el título en la lista y en la conversación abierta. */
export function useRenameConversation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.renameConversation,
    onSettled: (_data, _error, { id }) => {
      void client.invalidateQueries({ queryKey: queryKeys.conversations });
      void client.invalidateQueries({ queryKey: queryKeys.conversation(id) });
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

/** Texto de un fragmento citado; se pide al abrir la cita y no caduca mientras el documento siga. */
export function useFragment(conversationId: string | null, chunkId: string, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.fragment(conversationId ?? "", chunkId),
    queryFn: () => api.fragment(conversationId!, chunkId),
    enabled: enabled && conversationId !== null,
    staleTime: Infinity,
    retry: false,
  });
}
