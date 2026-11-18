"use client";

import { MenuIcon, PanelLeftCloseIcon, PanelLeftOpenIcon, PanelRightIcon, PlusIcon, SearchIcon } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, type ComponentProps, type ReactNode } from "react";

import { ApiStatus } from "@/components/api-status";
import { ConversationPanel } from "@/components/conversation-panel";
import { AppLogo } from "@/components/app-logo";
import { AppearanceMenu } from "@/components/appearance-menu";
import { ResizeHandle } from "@/components/resize-handle";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { ConversationList } from "@/features/conversations/conversation-list";
import { useMediaQuery } from "@/hooks/use-media-query";
import { enter, finishFirstEnter, useGSAP } from "@/lib/motion";
import { useChatStore } from "@/stores/chat-store";
import { useLayoutStore } from "@/stores/layout-store";
import { DOCKED_PANEL_QUERY, useUiStore } from "@/stores/ui-store";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{title}</h2>
      {children}
    </section>
  );
}

/** Lateral: las conversaciones. Los documentos son de cada conversación y viven en el chat (ADR-032). */
function Sidebar() {
  return (
    <Section title="Conversaciones">
      <ConversationList />
    </Section>
  );
}

/**
 * «Nueva conversación» en sus tres sitios: la cabecera (solo en pantallas sin lateral fijo), la cabecera
 * del lateral (con texto) y el riel (icono con tooltip). Desactivada mientras hay un turno en curso.
 */
function NewChatButton({ place }: { place: "header" | "sidebar" | "rail" }) {
  const busy = useChatStore((state) => state.busy);
  const content =
    place === "rail" ? (
      <PlusIcon aria-hidden />
    ) : (
      <>
        <PlusIcon aria-hidden /> <span className={place === "header" ? "hidden sm:inline" : undefined}>Nueva conversación</span>
      </>
    );
  const props = {
    variant: place === "rail" ? ("ghost" as const) : ("outline" as const),
    size: place === "rail" ? ("icon" as const) : ("sm" as const),
    className: place === "header" ? "lg:hidden" : place === "sidebar" ? "flex-1 justify-start" : undefined,
  };
  const button = busy ? (
    <Button {...props} disabled aria-label="Nueva conversación">
      {content}
    </Button>
  ) : (
    <Button asChild {...props}>
      <Link href="/" aria-label="Nueva conversación" onClick={() => useUiStore.getState().setSidebarOpen(false)}>
        {content}
      </Link>
    </Button>
  );
  if (place !== "rail" || busy) return button;
  return (
    <Tooltip>
      <TooltipTrigger asChild>{button}</TooltipTrigger>
      <TooltipContent side="right">Nueva conversación</TooltipContent>
    </Tooltip>
  );
}

/** Botón de la cabecera que abre y cierra el panel de la conversación (fijo en pantallas anchas). */
function PanelButton() {
  const docked = useMediaQuery(DOCKED_PANEL_QUERY);
  const panelOpen = useLayoutStore((state) => state.panelOpen);
  const sheetOpen = useUiStore((state) => state.panelSheetOpen);
  const open = docked ? panelOpen : sheetOpen;
  return (
    <Button
      id="panel-toggle"
      variant="ghost"
      size="sm"
      aria-label="Panel de la conversación"
      aria-expanded={open}
      aria-controls={docked ? "conversation-panel" : undefined}
      onClick={() => useUiStore.getState().togglePanel()}
    >
      <PanelRightIcon aria-hidden /> <span className="hidden lg:inline">Panel</span>
    </Button>
  );
}

/**
 * Pliega o despliega el lateral. El botón pulsado desaparece, así que el foco pasa al que hace lo
 * contrario o, si se indica, al control que se quiere usar (p. ej. el buscador).
 */
function toggleSidebar(collapsed: boolean, focus?: string) {
  useLayoutStore.getState().setCollapsed(collapsed);
  const target = focus ?? (collapsed ? "#sidebar-expand" : "#sidebar-collapse");
  requestAnimationFrame(() =>
    (document.querySelector<HTMLElement>(target) ?? document.querySelector<HTMLElement>("#sidebar-collapse"))?.focus(),
  );
}

/** Botón de icono del riel, con tooltip a la derecha (el riel no tiene sitio para texto). */
function RailButton({ label, onClick, children, ...props }: ComponentProps<typeof Button> & { label: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button variant="ghost" size="icon" aria-label={label} onClick={onClick} {...props}>
          {children}
        </Button>
      </TooltipTrigger>
      <TooltipContent side="right">{label}</TooltipContent>
    </Tooltip>
  );
}

/** Lateral plegado: una franja de iconos para desplegarlo o empezar una conversación. */
function SidebarRail() {
  return (
    // w-full: el lateral es una fila flexible; sin ancho propio el riel se encogería a la izquierda
    <nav aria-label="Lateral plegado" className="hidden w-full flex-col items-center gap-1 py-2 sidebar-collapsed:flex">
      <RailButton
        id="sidebar-expand"
        label="Mostrar conversaciones"
        aria-controls="sidebar"
        aria-expanded={false}
        onClick={() => toggleSidebar(false)}
      >
        <PanelLeftOpenIcon aria-hidden />
      </RailButton>
      <NewChatButton place="rail" />
      <RailButton label="Buscar conversaciones" onClick={() => toggleSidebar(false, "#sidebar [data-conversation-search]")}>
        <SearchIcon aria-hidden />
      </RailButton>
    </nav>
  );
}

/**
 * Dos columnas en escritorio (conversaciones · chat). Los pasos del agente son detalle
 * técnico que no hace falta a primera vista: se abren en un panel deslizante (Sheet) con el botón
 * «Pasos del agente» de la cabecera, en todas las anchuras. En pantallas pequeñas el lateral de
 * conversaciones también se abre así.
 *
 * Cada zona es un panel flotante con un hueco entre ellos. La geometría es la misma en todos los
 * estilos (al cambiar de Clásico a Glass nada se mueve): Glass solo cambia el relleno de los paneles
 * por cristal (`data-surface="bar"`, ver globals.css).
 *
 * El lateral y el panel de pasos se ensanchan con un separador (ResizeHandle). El ancho vive en las
 * variables CSS --sidebar-w y --trace-w, que un script pone antes de pintar (src/lib/layout.ts).
 */
export function AppShell({ children }: { children: ReactNode }) {
  const { sidebarOpen, panelSheetOpen, setSidebarOpen, setPanelSheetOpen } = useUiStore();

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
        <Button variant="ghost" size="icon" className="lg:hidden" onClick={() => setSidebarOpen(true)} aria-label="Abrir conversaciones">
          <MenuIcon aria-hidden />
        </Button>
        <h1 className="flex items-center gap-2 font-heading text-base font-semibold whitespace-nowrap">
          <AppLogo className="size-7" />
          {/* en pantallas muy estrechas (320 px) solo cabe el logo; el nombre sigue para lectores de pantalla */}
          <span className="max-[379px]:sr-only">TechDoc Agent</span>
        </h1>
        <div className="ml-auto flex items-center gap-2">
          <span className="hidden sm:inline-flex">
            <ApiStatus />
          </span>
          <NewChatButton place="header" />
          <AppearanceMenu />
          <PanelButton />
        </div>
      </header>

      <div className="flex min-h-0 flex-1 gap-2">
        {/* Plegado (data-sidebar="collapsed" en <html>, ver lib/layout.ts) mide lo que el riel; el contenido
            tiene ancho fijo y se recorta mientras el ancho se anima, así no se recoloca a cada fotograma. */}
        <aside
          id="sidebar"
          data-surface="bar"
          data-enter-item
          className="hidden w-(--sidebar-w) shrink-0 overflow-hidden rounded-xl border bg-card shadow-xs lg:flex sidebar-collapsed:w-14"
          aria-label="Conversaciones"
        >
          <SidebarRail />
          <div className="flex w-(--sidebar-w) min-w-(--sidebar-w) flex-col sidebar-collapsed:hidden">
            <div className="flex items-center gap-2 px-4 pt-3">
              <NewChatButton place="sidebar" />
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    id="sidebar-collapse"
                    variant="ghost"
                    size="icon-sm"
                    aria-label="Ocultar conversaciones"
                    aria-controls="sidebar"
                    aria-expanded
                    onClick={() => toggleSidebar(true)}
                  >
                    <PanelLeftCloseIcon aria-hidden />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Ocultar conversaciones</TooltipContent>
              </Tooltip>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto p-4">
              <Sidebar />
            </div>
          </div>
        </aside>
        {/* ocupa el hueco entre los dos paneles (-mx-2 compensa el gap) */}
        <ResizeHandle
          panel="sidebar"
          controls="sidebar"
          edge="end"
          collapsible
          label="Ancho del panel de conversaciones"
          className="-mx-2 hidden lg:block"
        />
        <main data-surface="bar" className="min-w-0 flex-1 overflow-hidden rounded-xl border bg-card shadow-xs">
          {children}
        </main>
        {/* Panel de la conversación fijo (pantallas anchas y data-panel="open" en <html>, ver lib/layout.ts).
            Es hermano del chat, no antecesor del compositor: su superficie no apaga el cristal. */}
        <ResizeHandle
          panel="trace"
          controls="conversation-panel"
          edge="start"
          closable
          label="Ancho del panel de la conversación"
          className="-mx-2 hidden xl:panel-open:block"
        />
        <aside
          id="conversation-panel"
          data-surface="bar"
          aria-label="Panel de la conversación"
          // max-w: también al encoger la ventana, el chat conserva 480 px (CHAT_MIN en lib/layout.ts)
          className="hidden w-(--trace-w) max-w-[calc(100vw-var(--sidebar-w)-33rem)] shrink-0 flex-col overflow-hidden rounded-xl border bg-card p-4 shadow-xs xl:panel-open:flex"
        >
          <ConversationPanel />
        </aside>
      </div>

      <Sheet open={sidebarOpen} onOpenChange={setSidebarOpen}>
        {/* Al abrirse, el foco va al panel y no a su primer control (el buscador): en un móvil sacaría el
            teclado sin pedirlo. Tab lleva al buscador y a las conversaciones. */}
        <SheetContent
          side="left"
          className="overflow-y-auto"
          onOpenAutoFocus={(event) => {
            event.preventDefault();
            (event.currentTarget as HTMLElement).focus();
          }}
        >
          <SheetHeader>
            <SheetTitle>TechDoc Agent</SheetTitle>
            <SheetDescription>Conversaciones</SheetDescription>
          </SheetHeader>
          <div className="px-4 pb-4">
            <Sidebar />
          </div>
        </SheetContent>
      </Sheet>
      {/* En pantallas estrechas el mismo panel se abre encima del chat */}
      <Sheet open={panelSheetOpen} onOpenChange={setPanelSheetOpen}>
        <SheetContent
          id="conversation-panel-sheet"
          side="right"
          className="flex flex-col data-[side=right]:w-(--trace-w) data-[side=right]:max-w-[calc(100vw-3rem)] data-[side=right]:sm:max-w-[calc(100vw-3rem)]"
        >
          <ResizeHandle
            panel="trace"
            controls="conversation-panel-sheet"
            edge="start"
            label="Ancho del panel de la conversación"
            className="absolute inset-y-0 -left-1 hidden sm:block"
          />
          <SheetHeader className="pb-0">
            <SheetTitle>Panel de la conversación</SheetTitle>
            <SheetDescription>Documentos, artefactos y pasos del agente de este chat</SheetDescription>
          </SheetHeader>
          <div className="flex min-h-0 flex-1 flex-col px-4 pb-4">
            <ConversationPanel />
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
