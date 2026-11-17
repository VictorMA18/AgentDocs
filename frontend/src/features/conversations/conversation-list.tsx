"use client";

import { EllipsisIcon, PencilIcon, SearchIcon, Trash2Icon, XIcon } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState, type RefObject } from "react";

import { ConfirmAction } from "@/components/confirm-action";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { errorMessage } from "@/lib/api/client";
import { useConversations, useDeleteConversation, useRenameConversation } from "@/lib/api/queries";
import { MAX_QUERY_CHARS, MAX_TITLE_CHARS, type ConversationSummary } from "@/lib/api/schemas";
import { findMatch } from "@/lib/highlight";
import { formatDate, groupByDate, plural } from "@/lib/labels";
import { notifyError, notifySuccess } from "@/lib/notify";
import { useChatStore } from "@/stores/chat-store";
import { useUiStore } from "@/stores/ui-store";

const SEARCH_DELAY_MS = 200; // espera tras la última tecla antes de buscar

/** Texto con la primera aparición de `query` resaltada (sin distinguir mayúsculas ni tildes). */
function Highlight({ text, query }: { text: string; query: string }) {
  const match = query ? findMatch(text, query) : null;
  if (!match) return text;
  const [start, end] = match;
  return (
    <>
      {text.slice(0, start)}
      {/* texto principal sobre el acento al 15 %: ≥ 6,4:1 en los 20 temas (el gris secundario daba 3,5:1) */}
      <mark className="rounded-sm bg-primary/15 text-foreground">{text.slice(start, end)}</mark>
      {text.slice(end)}
    </>
  );
}

/**
 * Buscador de conversaciones: busca en títulos, preguntas y respuestas (en el servidor). Esc borra la
 * búsqueda; el botón ✕ también. Lo enfoca el riel con su botón «Buscar conversaciones».
 */
function SearchField({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <div role="search" className="relative">
      <SearchIcon className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
      <input
        type="search"
        data-conversation-search
        aria-label="Buscar conversaciones"
        placeholder="Buscar" // corto: a 320 px «Buscar conversaciones» se cortaba (el nombre accesible es el completo)
        value={value}
        maxLength={MAX_QUERY_CHARS}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Escape" && value) {
            event.preventDefault();
            onChange("");
          }
        }}
        className="h-8 w-full rounded-md border bg-transparent pr-8 pl-8 text-base outline-none sm:text-sm placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 [&::-webkit-search-cancel-button]:appearance-none"
      />
      {value && (
        <Button
          variant="ghost"
          size="icon-xs"
          aria-label="Borrar la búsqueda"
          className="absolute top-1/2 right-1 -translate-y-1/2"
          onClick={(event) => {
            onChange("");
            (event.currentTarget.parentElement?.querySelector("input") as HTMLInputElement | null)?.focus();
          }}
        >
          <XIcon aria-hidden />
        </Button>
      )}
    </div>
  );
}

/**
 * Campo para renombrar en la misma fila: Intro o salir del campo guarda, Esc cancela. Se enfoca al
 * montarse, así se puede escribir enseguida, sin esperar a que el menú termine de cerrarse (y la fila
 * impide que el menú, al cerrarse, devuelva el foco a su botón).
 */
function RenameField({
  conv,
  field,
  onDone,
}: {
  conv: ConversationSummary;
  field: RefObject<HTMLInputElement | null>;
  /** Título nuevo, o `null` si se canceló o no cambió. */
  onDone: (title: string | null) => void;
}) {
  const cancelled = useRef(false);
  const done = useRef(false);
  useEffect(() => field.current?.focus(), [field]); // Intro y la pérdida de foco que le sigue no guardan dos veces

  function save(value: string) {
    if (done.current) return;
    done.current = true;
    const title = value.trim();
    onDone(cancelled.current || !title || title === conv.title ? null : title);
  }

  return (
    <form
      className="min-w-0 flex-1 px-1 py-1"
      onSubmit={(event) => {
        event.preventDefault();
        save(new FormData(event.currentTarget).get("title") as string);
      }}
    >
      <input
        ref={field}
        name="title"
        aria-label={`Nuevo título de la conversación ${conv.title}`}
        defaultValue={conv.title}
        maxLength={MAX_TITLE_CHARS}
        onFocus={(event) => event.currentTarget.select()}
        onBlur={(event) => save(event.currentTarget.value)}
        onKeyDown={(event) => {
          if (event.key !== "Escape") return;
          event.preventDefault();
          cancelled.current = true;
          event.currentTarget.blur();
        }}
        className="h-8 w-full rounded-md border bg-background px-2 text-base outline-none sm:text-sm focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
      />
    </form>
  );
}

function ConversationRow({
  conv,
  current,
  busy,
  query,
}: {
  conv: ConversationSummary;
  current: boolean;
  busy: boolean;
  query: string;
}) {
  const remove = useDeleteConversation();
  const rename = useRenameConversation(); // aquí y no en el campo: el campo se desmonta antes de que responda
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const field = useRef<HTMLInputElement>(null);
  const editingNext = useRef(false); // al cerrar el menú para renombrar, el foco va al campo, no al botón
  const closeSidebar = () => useUiStore.getState().setSidebarOpen(false);

  function onDelete() {
    remove.mutate(conv.id, {
      onSuccess: () => {
        notifySuccess(`Conversación «${conv.title}» quitada.`);
        if (current) {
          useChatStore.getState().reset();
          router.push("/");
        }
      },
      onError: (err) => notifyError(errorMessage(err)),
    });
  }

  return (
    <li className={`group flex items-center gap-1 rounded-md pr-1 hover:bg-muted ${current ? "bg-muted" : ""}`}>
      {editing ? (
        <RenameField
          conv={conv}
          field={field}
          onDone={(title) => {
            setEditing(false);
            requestAnimationFrame(() => menuButton.current?.focus());
            if (!title) return;
            rename.mutate(
              { id: conv.id, title },
              {
                onSuccess: (result) => notifySuccess(`Conversación renombrada a «${result.title}».`),
                onError: (err) => notifyError(errorMessage(err)),
              },
            );
          }}
        />
      ) : (
        <Link
          href={`/c/${conv.id}`}
          aria-current={current ? "page" : undefined}
          aria-disabled={busy}
          tabIndex={busy ? -1 : undefined}
          onClick={(event) => (busy ? event.preventDefault() : closeSidebar())}
          title={conv.title}
          className={`min-w-0 flex-1 px-2 py-1.5 ${busy ? "pointer-events-none opacity-60" : ""}`}
        >
          {/* hasta dos líneas: un título automático (≤ 60 caracteres) cabe entero; uno más largo, renombrado
              a mano, se lee completo en la pestaña al abrir la conversación y en el campo de renombrar */}
          <span className="line-clamp-2 text-sm break-words">
            <Highlight text={conv.title} query={query} />
          </span>
          {query && conv.snippet && (
            <span className="line-clamp-2 text-xs text-muted-foreground">
              <Highlight text={conv.snippet} query={query} />
            </span>
          )}
          <span className="block text-xs text-muted-foreground">
            {plural(conv.turns, "pregunta", "preguntas")} · {formatDate(conv.updated)}
          </span>
        </Link>
      )}
      {/* modal={false}: el menú abre un diálogo; si el menú fuera modal, Radix deja `pointer-events: none`
          en <body> al pasar de uno a otro y la página deja de responder al ratón. */}
      <DropdownMenu modal={false}>
        <DropdownMenuTrigger asChild>
          <Button
            ref={menuButton}
            variant="ghost"
            size="icon-sm"
            disabled={busy}
            aria-label={`Más opciones de la conversación ${conv.title}`}
            className="opacity-60 group-hover:opacity-100 focus-visible:opacity-100 data-[state=open]:opacity-100"
          >
            <EllipsisIcon aria-hidden />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align="end"
          onCloseAutoFocus={(event) => {
            if (!editingNext.current) return;
            editingNext.current = false;
            event.preventDefault();
            if (document.activeElement !== field.current) field.current?.focus();
          }}
        >
          <DropdownMenuItem
            onSelect={() => {
              editingNext.current = true;
              setEditing(true);
            }}
          >
            <PencilIcon aria-hidden /> Renombrar
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem variant="destructive" onSelect={() => setConfirming(true)}>
            <Trash2Icon aria-hidden /> Quitar
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <ConfirmAction
        open={confirming}
        onOpenChange={setConfirming}
        title={`¿Quitar la conversación «${conv.title}»?`}
        description="Se borrarán sus mensajes y lo que el agente recuerda de ella. No se puede deshacer."
        confirmLabel="Quitar conversación"
        onConfirm={onDelete}
      />
    </li>
  );
}

/**
 * Conversaciones guardadas, agrupadas por la fecha de su última actividad (Hoy, Ayer, Últimos 7 días,
 * Anteriores). Cada una se abre (enlace a /c/<id>) y, desde «Más opciones», se renombra o se quita.
 * Bloqueadas mientras hay un turno en curso.
 */
export function ConversationList() {
  const [input, setInput] = useState("");
  const [query, setQuery] = useState("");
  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(input.trim()), SEARCH_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [input]);
  const { data, error, isPending } = useConversations(query);
  const busy = useChatStore((state) => state.busy);
  const params = useParams<{ id?: string }>();
  const ids = useId(); // la lista se pinta dos veces (lateral y panel móvil): encabezados con id único

  const searching = query !== "";
  const search = (searching || (data?.length ?? 0) > 0) && <SearchField value={input} onChange={setInput} />;

  if (isPending) {
    return (
      <div className="space-y-2" aria-busy="true">
        <Skeleton className="h-10" />
        <Skeleton className="h-10" />
      </div>
    );
  }
  if (error) {
    return (
      <div className="space-y-3">
        {search}
        <p className="text-sm text-destructive">{errorMessage(error)}</p>
      </div>
    );
  }
  if (data.length === 0 && !searching) {
    return (
      <p className="text-sm text-muted-foreground">
        Aún no hay conversaciones guardadas. Se guardan solas al enviar el primer mensaje.
      </p>
    );
  }
  return (
    <div className="space-y-4">
      {search}
      {/* el número de resultados se anuncia a los lectores de pantalla al terminar cada búsqueda */}
      <p role="status" className={searching && data.length === 0 ? "text-sm text-muted-foreground" : "sr-only"}>
        {searching
          ? data.length === 0
            ? `Ninguna conversación contiene «${query}».`
            : `${plural(data.length, "conversación encontrada", "conversaciones encontradas")}`
          : ""}
      </p>
      {groupByDate(data).map((group, index) => (
        <section key={group.label} aria-labelledby={`${ids}-${index}`}>
          <h3 id={`${ids}-${index}`} className="mb-1 px-2 text-xs font-medium text-muted-foreground">
            {group.label}
          </h3>
          <ul className="space-y-1" aria-label={`Conversaciones de ${group.label.toLowerCase()}`}>
            {group.items.map((conv) => (
              <ConversationRow key={conv.id} conv={conv} current={conv.id === params.id} busy={busy} query={query} />
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
