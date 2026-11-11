"use client";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { errorMessage } from "@/lib/api/client";
import { useProviders } from "@/lib/api/queries";
import { providerIdSchema } from "@/lib/api/schemas";
import { useChatStore } from "@/stores/chat-store";

/**
 * Proveedor del LLM para el próximo turno (Fase 10, ADR-028). Se puede cambiar en cualquier turno;
 * la conversación recuerda el último. Los no disponibles salen deshabilitados con su motivo.
 */
export function ProviderSelect({ disabled }: { disabled: boolean }) {
  const { data, error, isPending } = useProviders();
  const chosen = useChatStore((state) => state.provider);

  if (error) return <p className="text-xs text-muted-foreground">Proveedores: {errorMessage(error)}</p>;

  // Siempre controlado: "" mientras cargan los proveedores (muestra el placeholder). Con `undefined`
  // el Select empezaría no controlado y pasaría a controlado al llegar los datos (aviso de React).
  const value = chosen ?? data?.find((p) => p.default)?.id ?? "";

  return (
    <div className="flex min-w-0 items-center gap-2 text-xs text-muted-foreground">
      <span id="provider-label">Modelo</span>
      <Select
        value={value}
        disabled={disabled || isPending}
        onValueChange={(next) => {
          const parsed = providerIdSchema.safeParse(next);
          if (parsed.success) useChatStore.getState().setProvider(parsed.data);
        }}
      >
        {/* min-w-0: con un proveedor no disponible el texto incluye su motivo; se recorta (line-clamp) en vez
            de desbordar a 320 px, y el motivo completo se lee al abrir la lista. */}
        <SelectTrigger size="sm" aria-labelledby="provider-label" className="min-w-0 text-xs" data-testid="provider-select">
          <SelectValue placeholder="Cargando…" />
        </SelectTrigger>
        <SelectContent>
          {data?.map((provider) => (
            <SelectItem key={provider.id} value={provider.id} disabled={!provider.available}>
              <span className="font-medium">{provider.label}</span>
              <span className="font-mono text-muted-foreground">{provider.model}</span>
              {!provider.available && provider.reason && (
                <span className="text-muted-foreground">· {provider.reason}</span>
              )}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
