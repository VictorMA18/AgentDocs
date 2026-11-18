"use client";

import { FileTextIcon, ListTreeIcon, ShapesIcon } from "lucide-react";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ArtifactsPanel } from "@/features/artifacts/artifacts-panel";
import { DocumentsPanel } from "@/features/documents/documents-panel";
import { AgentTrace } from "@/features/trace/agent-trace";
import { useUiStore, type PanelTab } from "@/stores/ui-store";

// sin icono si el panel es muy estrecho (container query): el texto de las tres pestañas siempre cabe
const TRIGGER = "min-w-0 text-muted-foreground data-active:text-foreground @max-[21rem]:[&_svg]:hidden";

/**
 * Panel de la conversación (Fase 12.C, ADR-033): todo lo que pertenece al chat abierto, en tres
 * pestañas (patrón Tabs de APG: flechas entre pestañas, Tab al contenido). Va fijo junto al chat en
 * pantallas anchas y encima, en un Sheet, en las estrechas; el contenido es el mismo.
 */
export function ConversationPanel() {
  const tab = useUiStore((state) => state.panelTab);
  const setTab = useUiStore((state) => state.setPanelTab);

  return (
    <Tabs value={tab} onValueChange={(value) => setTab(value as PanelTab)} className="@container flex min-h-0 flex-1 flex-col gap-3">
      <TabsList className="w-full">
        <TabsTrigger value="documents" className={TRIGGER}>
          <FileTextIcon aria-hidden /> Documentos
        </TabsTrigger>
        <TabsTrigger value="artifacts" className={TRIGGER}>
          <ShapesIcon aria-hidden /> Artefactos
        </TabsTrigger>
        <TabsTrigger value="steps" className={TRIGGER}>
          <ListTreeIcon aria-hidden /> Pasos
        </TabsTrigger>
      </TabsList>
      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
        <TabsContent value="documents">
          <DocumentsPanel />
        </TabsContent>
        <TabsContent value="artifacts">
          <ArtifactsPanel />
        </TabsContent>
        <TabsContent value="steps">
          <AgentTrace />
        </TabsContent>
      </div>
    </Tabs>
  );
}
