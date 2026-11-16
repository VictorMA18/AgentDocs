"use client";

import { ListTreeIcon, MenuIcon, PlusIcon } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, type ReactNode } from "react";

import { ApiStatus } from "@/components/api-status";
import { AppearanceMenu } from "@/components/appearance-menu";
import { ResizeHandle } from "@/components/resize-handle";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { ConversationList } from "@/features/conversations/conversation-list";
import { DocumentList } from "@/features/documents/document-list";
import { UploadDropzone } from "@/features/documents/upload-dropzone";
import { AgentTrace } from "@/features/trace/agent-trace";
import { enter, finishFirstEnter, useGSAP } from "@/lib/motion";
import { useChatStore } from "@/stores/chat-store";
import { useLayoutStore } from "@/stores/layout-store";
import { useUiStore } from "@/stores/ui-store";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{title}</h2>
      {children}
    </section>
  );
}

function Sidebar() {
  return (
    <div className="space-y-6">
      <Section title="Conversaciones">
        <ConversationList />
      </Section>
      <Separator />
      <Section title="Documentos">
        <UploadDropzone />
        <DocumentList />
      </Section>
    </div>
  );
}

function NewChatButton() {
  const busy = useChatStore((state) => state.busy);
  if (busy) {
    return (
      <Button variant="outline" size="sm" disabled aria-label="Nueva conversación">
        <PlusIcon aria-hidden /> <span className="hidden sm:inline">Nueva conversación</span>
      </Button>
    );
  }
  return (
    <Button asChild variant="outline" size="sm">
      <Link href="/" aria-label="Nueva conversación" onClick={() => useUiStore.getState().setSidebarOpen(false)}>
        <PlusIcon aria-hidden /> <span className="hidden sm:inline">Nueva conversación</span>
      </Link>
    </Button>
  );
}

/**
 * Dos columnas en escritorio (conversaciones y documentos · chat). Los pasos del agente son detalle
 * técnico que no hace falta a primera vista: se abren en un panel deslizante (Sheet) con el botón
 * «Pasos del agente» de la cabecera, en todas las anchuras. En pantallas pequeñas el lateral de
 * conversaciones y documentos también se abre así.
 *
 * Cada zona es un panel flotante con un hueco entre ellos. La geometría es la misma en todos los
 * estilos (al cambiar de Clásico a Glass nada se mueve): Glass solo cambia el relleno de los paneles
 * por cristal (`data-surface="bar"`, ver globals.css).
 *
 * El lateral y el panel de pasos se ensanchan con un separador (ResizeHandle). El ancho vive en las
 * variables CSS --sidebar-w y --trace-w, que un script pone antes de pintar (src/lib/layout.ts).
 */
export function AppShell({ children }: { children: ReactNode }) {
  const { sidebarOpen, traceOpen, setSidebarOpen, setTraceOpen } = useUiStore();

  // Anchos guardados en el store (el CSS ya los tiene desde antes de pintar; esto pone aria-valuenow).
  useEffect(() => useLayoutStore.getState().load(), []);

  // Primera carga: cabecera y lateral entran en escalón (GSAP; solo fundido con movimiento reducido).
  // El panel del chat no se anima: un filter u opacity en él apagaría el cristal del compositor.
  const shell = useRef<HTMLDivElement>(null);
  useGSAP(
    () => {
      enter(["header", "#sidebar"]);
      finishFirstEnter();
    },
    { scope: shell },
  );

  return (
    <div ref={shell} className="flex h-dvh flex-col gap-2 p-2">
      <header data-surface="bar" data-enter-item className="flex h-14 shrink-0 items-center gap-2 rounded-xl border bg-card px-3 shadow-xs">
        <Button variant="ghost" size="icon" className="lg:hidden" onClick={() => setSidebarOpen(true)} aria-label="Abrir conversaciones y documentos">
          <MenuIcon aria-hidden />
        </Button>
        <h1 className="font-heading text-base font-semibold whitespace-nowrap">TechDoc Agent</h1>
        <div className="ml-auto flex items-center gap-2">
          <span className="hidden sm:inline-flex">
            <ApiStatus />
          </span>
          <NewChatButton />
          <AppearanceMenu />
          <Button variant="ghost" size="sm" onClick={() => setTraceOpen(true)} aria-label="Ver los pasos del agente">
            <ListTreeIcon aria-hidden /> <span className="hidden lg:inline">Pasos del agente</span>
          </Button>
        </div>
      </header>

      <div className="flex min-h-0 flex-1 gap-2">
        <aside
          id="sidebar"
          data-surface="bar"
          data-enter-item
          className="hidden w-(--sidebar-w) shrink-0 overflow-y-auto rounded-xl border bg-card p-4 shadow-xs lg:block"
          aria-label="Conversaciones y documentos"
        >
          <Sidebar />
        </aside>
        {/* ocupa el hueco entre los dos paneles (-mx-2 compensa el gap) */}
        <ResizeHandle
          panel="sidebar"
          controls="sidebar"
          edge="end"
          label="Ancho del panel de conversaciones y documentos"
          className="-mx-2 hidden lg:block"
        />
        <main data-surface="bar" className="min-w-0 flex-1 overflow-hidden rounded-xl border bg-card shadow-xs">
          {children}
        </main>
      </div>

      <Sheet open={sidebarOpen} onOpenChange={setSidebarOpen}>
        <SheetContent side="left" className="overflow-y-auto">
          <SheetHeader>
            <SheetTitle>TechDoc Agent</SheetTitle>
            <SheetDescription>Conversaciones y documentos</SheetDescription>
          </SheetHeader>
          <div className="px-4 pb-4">
            <Sidebar />
          </div>
        </SheetContent>
      </Sheet>
      <Sheet open={traceOpen} onOpenChange={setTraceOpen}>
        <SheetContent
          id="trace-panel"
          side="right"
          className="overflow-y-auto data-[side=right]:w-(--trace-w) data-[side=right]:max-w-[calc(100vw-3rem)] data-[side=right]:sm:max-w-[calc(100vw-3rem)]"
        >
          <ResizeHandle
            panel="trace"
            controls="trace-panel"
            edge="start"
            label="Ancho del panel de pasos del agente"
            className="absolute inset-y-0 -left-1 hidden sm:block"
          />
          <SheetHeader>
            <SheetTitle>Pasos del agente</SheetTitle>
            <SheetDescription>Herramientas que usó en cada respuesta</SheetDescription>
          </SheetHeader>
          <div className="px-4 pb-4">
            <AgentTrace />
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
