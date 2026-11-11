"use client";

import { ListTreeIcon, MenuIcon, PlusIcon } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { ApiStatus } from "@/components/api-status";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { ConversationList } from "@/features/conversations/conversation-list";
import { DocumentList } from "@/features/documents/document-list";
import { UploadDropzone } from "@/features/documents/upload-dropzone";
import { AgentTrace } from "@/features/trace/agent-trace";
import { useChatStore } from "@/stores/chat-store";
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
 * Tres columnas en escritorio (conversaciones y documentos · chat · pasos del agente). En pantallas
 * pequeñas los laterales se abren como paneles deslizantes (Sheet) desde la cabecera.
 */
export function AppShell({ children }: { children: ReactNode }) {
  const { sidebarOpen, traceOpen, setSidebarOpen, setTraceOpen } = useUiStore();

  return (
    <div className="flex h-dvh flex-col">
      <header className="flex h-14 shrink-0 items-center gap-2 border-b px-3">
        <Button variant="ghost" size="icon" className="lg:hidden" onClick={() => setSidebarOpen(true)} aria-label="Abrir conversaciones y documentos">
          <MenuIcon aria-hidden />
        </Button>
        <h1 className="font-heading text-base font-semibold whitespace-nowrap">TechDoc Agent</h1>
        <div className="ml-auto flex items-center gap-2">
          <span className="hidden sm:inline-flex">
            <ApiStatus />
          </span>
          <NewChatButton />
          <ThemeToggle />
          <Button variant="ghost" size="icon" className="xl:hidden" onClick={() => setTraceOpen(true)} aria-label="Ver los pasos del agente">
            <ListTreeIcon aria-hidden />
          </Button>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <aside className="hidden w-72 shrink-0 overflow-y-auto border-r p-4 lg:block" aria-label="Conversaciones y documentos">
          <Sidebar />
        </aside>
        <main className="min-w-0 flex-1">{children}</main>
        <aside className="hidden w-80 shrink-0 overflow-y-auto border-l p-4 xl:block" aria-label="Pasos del agente">
          <Section title="Pasos del agente">
            <AgentTrace />
          </Section>
        </aside>
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
        <SheetContent side="right" className="overflow-y-auto">
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
