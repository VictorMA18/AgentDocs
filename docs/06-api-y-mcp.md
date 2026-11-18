# 06 · API (FastAPI), interfaz web (Next.js) y servidor MCP

La API y el servidor MCP son **adaptadores delgados**: validan entrada, llaman al núcleo, formatean salida. Ninguna lógica de agente ni de RAG vive aquí. La interfaz web es una aplicación aparte (`frontend/`) que **solo** habla con la API por HTTP (sección C).

## A. FastAPI

### Endpoints
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/healthz` | `{"status":"ok","documents":N,"chunks":M}` |
| POST | `/api/chat` | Cuerpo: `{"session_id": "...", "message": "..."}` |
| POST | `/api/chat/stream` | Mismo cuerpo; respuesta SSE (`text/event-stream`) con el progreso del turno y, al final, `final` o `error` |
| POST | `/api/conversations/{id}/documents` | Sube un documento a esa conversación (`multipart/form-data`, campo `file`). La primera subida crea la conversación, con el nombre del documento como título (Fase 12.B, ADR-032) |
| GET | `/api/conversations/{id}/documents` | Documentos de la conversación con sus fragmentos (vacío si no tiene; no crea nada en disco) |
| DELETE | `/api/conversations/{id}/documents/{source}` | Quita un documento de esa conversación |
| GET | `/api/conversations/{id}/documents/{source}` | Vista previa: los fragmentos del documento en orden (`{source, chunks: [{id, n, section, text}]}`), tal como se indexaron; sirve igual para un PDF (Fase 12.C) |
| GET | `/api/conversations/{id}/fragments/{chunk_id}` | Texto de un fragmento citado (`taskflow.md#4`, con el `#` codificado): `{id, source, text}`. 404 con qué hacer si ya no está |
| GET | `/api/conversations` | Conversaciones guardadas (`id`, `title`, `updated`, `turns`), las más recientes primero. Con `?q=` (≤ 100 caracteres), solo las que lo contienen en el título, una pregunta o una respuesta, sin distinguir mayúsculas ni tildes; si no está en el título, `snippet` trae ~90 caracteres alrededor (Fase 12.A) |
| GET | `/api/conversations/{id}` | Conversación completa con todos sus turnos |
| PATCH | `/api/conversations/{id}` | Renombra: `{"title": "..."}` (1-120 caracteres; los espacios se colapsan). No cambia `updated`, así que la lista no se reordena (Fase 12.A) |
| DELETE | `/api/conversations/{id}` | Borra la transcripción y la memoria del agente (en RAM y en disco) |
| GET | `/api/artifacts` | Lista de artefactos generados |
| GET | `/api/artifacts/{name}` | Descarga un artefacto (nombre validado) |
| GET | `/api/providers` | Proveedores del LLM: `id`, `label`, `model`, `available`, `reason`, `default` (nunca la clave; Fase 10) |

### Códigos de estado
| Código | Cuándo |
|---|---|
| 201 | Documento subido e indexado (`{"source", "chunks", "warnings"}`) |
| 400 | Nombre no válido, archivo vacío o sin contenido indexable, nombre de artefacto o de documento con formato incorrecto |
| 404 | Documento o artefacto inexistente (también rutas con `..` o enlaces simbólicos que salen de `outputs/`) |
| 413 | Archivo mayor que `MAX_UPLOAD_MB` |
| 415 | Extensión fuera de `ALLOWED_EXTENSIONS` |
| 409 | El proveedor pedido (o el de la conversación) no está disponible: el mensaje da el motivo y pide elegir otro |
| 422 | Cuerpo de `/api/chat` inválido (`session_id` con `^[A-Za-z0-9_-]{8,64}$`, mensaje de 1 a 8.000 caracteres, `provider` distinto de `claude` o `gemini`) |
| 502 | El LLM falló; el mensaje es genérico y el detalle va al log |
| 503 | El proveedor no se puede usar ahora (`LLMUnavailableError`: cuota de Gemini agotada, falta la clave, CLI de Claude ausente o sin sesión); el mensaje dice qué hacer |

### Respuesta de `/api/chat`
```json
{
  "reply": "Para configurar reintentos... [taskflow.md#3]",
  "tool_calls": [
    {"tool": "buscar_documentos", "args": {"query": "configurar reintentos"}, "is_error": false, "duration_ms": 41}
  ],
  "artifacts": [{"name": "diagrama-encolar-3f2a.mmd", "type": "mermaid", "title": "Encolar y procesar"}],
  "usage": {"input_tokens": 2410, "output_tokens": 312},
  "truncated": false,
  "llm": {"provider": "claude", "model": "claude-haiku-5-5"}
}
```

**Proveedor del turno (Fase 10, ADR-028):** el cuerpo admite `"provider": "claude" | "gemini"`. Sin él se usa el último de la conversación y, si no hay, `LLM_PROVIDER`. Se puede cambiar en cualquier turno: la memoria es texto plano y ambos usan el mismo protocolo, así que el otro modelo continúa con el contexto. `llm` dice quién respondió; se guarda en la transcripción y en el log (evento `turn_llm`). `GET /api/conversations` y `/api/conversations/{id}` incluyen `provider` (el del último turno; `null` en conversaciones anteriores). Los clientes se crean la primera vez que se piden y se reutilizan.

Cada chat correcto se guarda en la transcripción de su `session_id` (`message` y los mismos campos que la respuesta, más `ts`); uno fallido (422, 502) no crea nada. El id de las rutas de conversaciones debe cumplir `^[A-Za-z0-9_-]{8,64}$` (400 si no) y una conversación inexistente da 404. La memoria del agente también se guarda, así que tras reiniciar el servidor el siguiente mensaje continúa con el contexto.

`artifacts` lista los archivos que `generar_diagrama` y `generar_requisitos` guardaron **en ese turno**: el nombre sale del resultado de la herramienta (`ToolTrace.result`), el título de sus argumentos y el tipo de la extensión (`.mmd` → `mermaid`, `.md` → `requirements`). `GET /api/artifacts` devuelve `name`, `type`, `size` y `modified` de todos los archivos válidos de `outputs/`.

### Progreso en vivo: `POST /api/chat/stream` (Fase 8, ADR-020)
Es **progreso, no tokens**: el modelo devuelve su respuesta dentro de un JSON estructurado y no se puede emitir a medias. Eventos (`event:` con el tipo, `data:` con el JSON, una línea cada uno):

| Evento | Datos | Cuándo |
|---|---|---|
| `en_cola` | — | otro turno tiene el candado; este espera |
| `pensando` | `iter` | antes de cada llamada al modelo |
| `herramienta` | `nombre`, `resumen`, `ms`, `error` | tras cada herramienta |
| `final` | los mismos campos que la respuesta de `/api/chat` | el turno terminó bien (último evento) |
| `error` | `detalle` (mensaje genérico, sin trazas) | el modelo falló o hubo un error interno (último evento) |

Cada 15 s sin eventos se envía un comentario `: keepalive` para que un proxy no cierre la conexión. Cabeceras `Cache-Control: no-cache` y `X-Accel-Buffering: no`. La validación del cuerpo (422) ocurre antes de empezar a transmitir. El turno corre en un hilo y usa el mismo candado y la misma transcripción que `/api/chat`; si el cliente se desconecta, el turno termina y se guarda igualmente. La interfaz lo lee con `fetch` (EventSource solo admite GET) y valida cada evento con Zod (sección C).

### Sin páginas (Fase 9.B, ADR-026)
El backend es una **API pura**: no sirve HTML ni estáticos (`/` responde 404). La antigua página en HTML/JS puro (`api/static/`) se retiró al alcanzar la paridad con el frontend Next.js (sección C).

### Reglas
- Límite de tamaño de subida (`MAX_UPLOAD_MB`) y lista blanca de extensiones. Se rechaza antes de leer el cuerpo si `Content-Length` ya lo supera (mejor esfuerzo: sin esa cabecera, el servidor puede haber recibido parte del archivo) y se aborta durante la lectura al pasar el límite.
- Nombre de archivo **saneado** (ADR-014): sin carpetas, solo `[A-Za-z0-9._-]`, sin punto inicial, hasta 100 caracteres. No se genera uno nuevo porque ese nombre es la fuente de las citas (`[archivo#n]`); subir el mismo nombre reemplaza el documento. Se guarda en `backend/data/chats/<id>/documents/`, la carpeta de esa conversación (ADR-032).
- `GET /api/artifacts/{name}`: solo `^[a-z0-9][a-z0-9._-]*$` con extensión `.mmd` o `.md`, sin `..`, resuelto dentro de `outputs/` (un enlace simbólico que salga se rechaza). Se sirve como `text/plain` con `Content-Disposition: attachment`.
- **CORS** (Fase 9, ADR-025): solo los orígenes de `CORS_ORIGINS` (por defecto `http://localhost:3000` y `http://127.0.0.1:3000`, el frontend Next.js en desarrollo), métodos `GET`, `POST`, `PATCH` y `DELETE` y cabecera `Content-Type`; cualquier otro origen no recibe cabeceras `Access-Control-*`. El middleware de CORS va por fuera del de seguridad, así que también el rechazo temprano (413) lleva la cabecera y el frontend puede leer el error. Cabeceras en todas las respuestas: `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'; …` (API pura: nada que cargar ni ejecutar; la CSP de la interfaz está en `frontend/next.config.ts`), `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`. `/docs`, `/redoc` y `/openapi.json` están desactivados.
- Un único candado serializa chat, subida y borrado (la memoria y el almacén JSON no son seguros ante hilos). Pensado para un usuario local; con varios usuarios habría que usar un candado por sesión.
- `POST /api/chat/stream`: SSE de progreso (ver arriba); `/api/chat` se conserva.

### Apariencia (Fase 11, ADR-029 y ADR-030)
- **Menú «Apariencia»** en la cabecera, con cinco grupos siempre visibles (el panel no cambia de alto): **Estilo** (Clásico o Glass), **Tema** (Claro, Oscuro o Sistema; en Glass es la base blanca o negra del cristal), **Color** (muestras Neutro, Rojo, Azul, Verde y Naranja con su nombre; la elegida pasa de cuadrado redondeado a círculo, con anillo y ✓; en Clásico tiñe el acento y en Glass también el fondo), **Fondo** (En movimiento o Quieto: la mancha central de Glass deriva despacio; el grupo se desactiva con el motivo a la vista en Clásico o si el sistema pide menos movimiento) y **Fuente** (Geist o DM Sans, válidas con cualquier estilo). Se guarda en `localStorage` (`techdoc-appearance`) y la luminosidad, como antes, en el `theme` de next-themes.
- **Cuatro atributos en `<html>`:** `data-style`, `data-tint`, `data-font` y `data-motion`; la clase `.dark` sigue marcando la luminosidad. Un script en `layout.tsx` los pone antes de pintar, a partir de `appearanceScript()` (`src/lib/appearance.ts`), y solo acepta valores conocidos.
- **Paneles ajustables:** el lateral y el panel de pasos se ensanchan con un separador (rol `separator`): se arrastra, se mueve con las flechas (16 px) e Inicio/Fin, y un clic pasa al tamaño siguiente. El ancho se guarda en `localStorage` (`techdoc-layout`) y un script lo pone antes de pintar como `--sidebar-w` y `--trace-w` (`src/lib/layout.ts`).
- **Animaciones (GSAP):** la primera carga (cabecera y lateral en escalón), el estado vacío y cada mensaje nuevo entran con fundido, 12 px y 4 px de desenfoque (300 ms; `src/lib/motion.ts`); con movimiento reducido, solo fundido. Nunca se anima un antecesor del compositor.
- **Barras de desplazamiento** finas con el color del texto secundario de cada tema (`--scrollbar-thumb`), iguales en todos los paneles; el pulgar cumple 3:1 contra el panel (medido en el E2E).
- **Paneles flotantes:** cabecera, lateral y chat son paneles con un hueco entre ellos, con la misma geometría en todos los estilos. El compositor va pegado abajo (`sticky`) dentro de la zona que se desplaza; los mensajes pasan por detrás y se desvanecen bajo él, y al final el último queda encima. La zona reserva el alto del compositor como `scroll-padding`, así un control enfocado con el teclado nunca queda tapado.
- **Glass** (`globals.css`): tokens en HSL que salen de `--tint-h` y `--tint-s` (tinte neutro en la 11.A) y superficies de cristal aplicadas por `data-slot` (tarjetas, menús, diálogos, paneles) y `data-surface` (`bar` en cabecera, laterales y chat; `panel` en el compositor). Los paneles grandes son translúcidos sin `backdrop-filter`: en Chrome un antecesor con `backdrop-filter` o `mask` impide que el compositor desenfoque los mensajes. Sin `backdrop-filter` o con `prefers-reduced-transparency` las superficies son opacas.
- **Al cambiar** de estilo, tema o fuente, la página se funde en 220 ms con la View Transitions API (`smoothly()` en `appearance-store.ts`; inmediato sin soporte o con movimiento reducido) y se apagan las transiciones CSS un fotograma para que nada se anime por su cuenta.

### Lateral, conversaciones y lectura (Fase 12.A, ADR-031)
- **Marca:** el icono (`frontend/brand/techdoc-agent.png`, del autor, con acabado de cristal) se recreó en SVG con la misma geometría y los mismos degradados (error medio de 1–5 niveles de 255 por zona), con fondo transparente y borde nítido; las fuentes están en `frontend/brand/`. La pestaña del navegador usa el dibujo completo, por decisión del autor: `src/app/icon.svg` (el navegador lo dibuja a la resolución de la pantalla) y, como respaldo, `favicon.ico` con el mismo dibujo reducido a 16, 32 y 48 px. `apple-icon.png` (180 px, a sangre) sale también de él. En la cabecera va en línea (`components/app-logo.tsx`), nítido a cualquier densidad; por debajo de 380 px de ancho solo se ve el logo y el nombre queda para lectores de pantalla.
- **Título de la pestaña:** el de la conversación abierta (`<title>` de React en `ChatView`; el `metadata` de `layout.tsx` ya no lleva `title`, porque el navegador usa el primer `<title>` y el de Next ganaba).
- **Lateral plegable a un riel de 56 px** con «Mostrar conversaciones» y «Nueva conversación» (iconos con tooltip). Se pliega arrastrando el separador por debajo del mínimo menos 64 px (hoy 178 px, con el mínimo de 242 que fijó el autor) (mientras tanto el lateral se atenúa y la línea se marca; se pliega al soltar), con Intro en el separador (patrón *Window Splitter* de APG), con la flecha que lo estrecha ya en el mínimo, con un clic tras el máximo o con el botón «Ocultar» de su cabecera. Al desplegar vuelve al ancho que tenía. El estado se guarda en `techdoc-layout` (`collapsed`) y un script pone `data-sidebar="collapsed"` en `<html>` antes de pintar; el CSS (variante `sidebar-collapsed:`) muestra el riel o el contenido, así React no pinta el estado guardado. Solo plegar y desplegar animan el ancho (200 ms; nada con movimiento reducido). El foco pasa al botón que hace lo contrario. En móvil el lateral sigue siendo un panel deslizante.
- **«Nueva conversación»** está arriba del lateral (y en el riel); en la cabecera solo aparece en pantallas sin lateral fijo.
- **Buscador de conversaciones** encima de la lista: busca en el servidor (título, preguntas y respuestas), espera 200 ms tras la última tecla, resalta lo encontrado (`<mark>`, texto principal sobre el acento al 15 %), enseña el fragmento cuando la coincidencia no está en el título y anuncia el número de resultados (`role="status"`). Esc o ✕ borran la búsqueda. El riel tiene un botón «Buscar conversaciones» que despliega el lateral y enfoca el buscador. Los títulos ocupan hasta dos líneas.
- **Conversaciones por fecha:** grupos Hoy, Ayer, Últimos 7 días y Anteriores (`groupByDate` en `src/lib/labels.ts`, por días de calendario locales). Cada fila tiene «Más opciones» (menú de shadcn, no modal) con **Renombrar** (campo en la misma fila, enfocado al aparecer: Intro o salir del campo guarda, Esc cancela, el foco vuelve al botón) y **Quitar** (con confirmación).
- **Una sola columna de lectura:** mensajes, código, diagramas y compositor miden `--chat-w` (38rem) y el texto de preguntas y respuestas va a 16 px (`text-chat`): ~72 caracteres por línea con Geist y con DM Sans (medido en el navegador; con 42rem y 15 px salían ~90).

### Documentos en el chat (Fase 12.B, ADR-032)
- **Cada conversación tiene sus documentos.** El lateral queda solo para las conversaciones; los documentos se ven y se gestionan dentro del chat.
- **Tres formas de adjuntar** (varios a la vez): el clip del compositor, el botón «Añadir» de la barra y soltar archivos en cualquier parte del chat (una capa avisa «Suelta para añadir a esta conversación»). En un chat nuevo se crea el id de la conversación y se pasa a `/c/<id>` en cuanto entra el primer documento; si no entra ninguno, el chat nuevo sigue siéndolo. Los éxitos se avisan juntos en un solo aviso; cada error, enseguida y con su motivo. La subida vive en un store global (`stores/upload-store.ts`) porque la vista se vuelve a montar al cambiar de ruta.
- **Barra de documentos** encima de los mensajes (`features/documents/document-bar.tsx`): un chip por documento con su tipo, su nombre completo (se parte, no se corta), sus fragmentos y «Quitar» con confirmación, y otro «Indexando…» por cada subida en curso (anunciado a los lectores de pantalla). En pantallas estrechas se pliega tras un botón «Documentos · N».
- **Tipo por extensión** (`components/file-type.tsx`): icono y etiqueta (MD, TXT, PDF, PY, JS, TS, JAVA, JSON, YAML) con un tono por familia (texto azul, PDF ámbar, código violeta, datos verde azulado; ninguno rojo, para no confundirse con el error). La etiqueta va siempre escrita: el tipo no depende del color.
- **Citas interactivas** (`features/chat/citations.tsx`): un plugin de remark propio convierte `[archivo#n]` (fuera del código y de los enlaces) en un `<cite data-chunk>` que `rehype-sanitize` admite, y se pinta como un botón con el tipo, el nombre y el fragmento (contado desde 1). Al pulsarlo, un popover pide el fragmento a la API y lo muestra con el mismo Markdown saneado que las respuestas. Si ya no existe, lo dice y explica que hay que volver a adjuntar el documento.
- **Chat vacío:** sin documentos invita a adjuntarlos; con documentos propone cuatro preguntas (resumen, conceptos clave, diagrama de flujo y requisitos funcionales) que se envían al pulsarlas.
- **Estado de la API:** su aviso ya no cuenta documentos (los de `/healthz` son los del índice global, no los de la web).

### Panel de la conversación, artefactos y avisos (Fase 12.C, ADR-033)
- **Panel de la conversación** (`components/conversation-panel.tsx`): todo lo que pertenece al chat abierto, en tres pestañas (patrón Tabs de APG): **Documentos** (la lista completa con tipo, fragmentos y «Quitar»; subidas en curso; «Adjuntar documentos»), **Artefactos** y **Pasos** (el antiguo panel de pasos del agente). A partir de 1280 px va **fijo junto al chat** (`aside`, con separador para ensancharlo; se recuerda abierto con `panelOpen` en `techdoc-layout` y `data-panel="open"` en `<html>` antes de pintar); por debajo se abre **encima** en un Sheet. Lo abre y cierra el botón «Panel» de la cabecera (`aria-expanded`).
- **Artefactos** (`features/artifacts/`): los diagramas y requisitos de la conversación salen de los turnos en pantalla (`turn.artifacts`): no hay endpoint nuevo. La lista, del más reciente al más antiguo, dice el tipo y la pregunta que lo generó; al elegir uno se ve en grande (el panel se ensancha hasta 560 px si es más estrecho) con Descargar, Copiar código, «Ver en el chat» (desplaza a su tarjeta y la enfoca) y vuelta a la lista. Cada tarjeta del chat tiene «Abrir en el panel».
- **Vista previa de documentos:** en la pestaña Documentos, pulsar un documento muestra sus fragmentos en orden, numerados como las citas (fragmento 3 = `[archivo#2]`) y con su sección: Markdown saneado, código en un bloque y texto (PDF, TXT) tal cual.
- **Anchos:** el lateral llega como mucho a 360 px; el panel de la conversación, a lo que deje al chat al menos 480 px (`maxWidth` y `CHAT_MIN` en `lib/layout.ts`, también con CSS al encoger la ventana). Arrastrar el borde del panel por debajo de su mínimo menos 64 px lo cierra al soltar (mientras tanto se atenúa); también Intro en el separador o la flecha que lo estrecha ya en el mínimo. Al reabrirlo vuelve a su ancho anterior y el foco pasa al botón «Panel».
- **Barra de documentos compacta:** una línea encima de los mensajes, «N documentos» con hasta tres insignias de tipo, que abre la pestaña Documentos; «Indexando…» y «Añadir».
- **Avisos** (`lib/notify.ts`, `components/ui/sonner.tsx`, `.app-toast` en `globals.css`): tarjeta del design system (cristal en Glass) con un icono en un círculo del tono semántico (el fondo no se tiñe), título, detalle en gris y, si tiene sentido, una acción («Ver documentos» abre el panel). Arriba a la derecha, bajo la cabecera. Los errores no se cierran solos; los éxitos, a los 5 s. Sonner va `unstyled` y sus reglas propias (sin capa) se anulan con selectores de más especificidad fuera de `@layer`.
- **«Nueva conversación»:** secundario relleno de 32 px a todo el ancho del lateral (la altura del buscador), con el atajo Ctrl/⌘+Shift+O visible si cabe; en la cabecera y el riel, botón de icono con tooltip. El acento queda para Enviar. El botón de ocultar el lateral va junto al título «Conversaciones»: en el ancho mínimo del lateral no cabían los dos en una fila sin recortar el texto.
- **Mínimo del panel: 360 px**, lo que necesitan las tres pestañas; si aun así no caben con su icono, los iconos se ocultan (container query) y el texto se lee entero.

### Organización del código (Fase 9.A, ADR-025)
`api/main.py` es solo el punto de entrada (`app`). `api/app.py` ensambla la aplicación (lifespan, middleware de seguridad, CORS, routers); `api/routers/` tiene un módulo por recurso (`chat.py`, `conversations.py`, `documents.py`, `artifacts.py`, `health.py`); `api/deps.py` define `Core` y la dependencia `get_core`; `api/schemas.py`, los modelos de entrada; y `api/security.py`, la CSP, el tope de subida y la validación de nombres.

### Cómo arrancar
```bash
cd backend
uvicorn techdoc_agent.api.main:app --reload     # API en http://127.0.0.1:8000
```
La interfaz se arranca aparte desde `frontend/` (sección C).
Al arrancar carga el modelo de embeddings y abre el almacén según `VECTOR_STORE`. `create_app(agent, store, embedder)` permite inyectar un núcleo falso en los tests (`tests/api/`).

## B. Servidor MCP

### Qué es MCP aquí
Un protocolo estándar para que **otros clientes** (Claude Desktop, Claude Code, otro agente) usen tus herramientas sin pasar por tu interfaz web. Se implementa con el SDK oficial de Python (`mcp` 2.x: `MCPServer`, antes `FastMCP`; ver ADR-016) en `src/techdoc_agent/mcp_server.py`.

### Herramientas expuestas
| Herramienta MCP | Qué hace | ¿Usa LLM interno? |
|---|---|---|
| `buscar_documentos(query, top_k, source)` | Búsqueda directa en el índice | No |
| `listar_documentos()` | Documentos indexados | No |
| `ingestar_documento(ruta)` | Indexa un archivo local (ruta validada contra directorio permitido) | No |
| `preguntar_agente(pregunta, session_id)` | Ejecuta el agente completo y devuelve la respuesta | **Sí** |

Cómo se comporta cada una:
- `buscar_documentos` y `listar_documentos` **delegan** en las herramientas RAG del agente (`rag_tools` vía `ToolRegistry.dispatch`): mismas validaciones, mismos umbrales (`MIN_SCORE` y `LEXICAL_MIN`), mismo modo de búsqueda (`SEARCH_MODE`) y mismo formato `<documento>`; el servidor no reimplementa nada.
- `ingestar_documento(ruta)`: `ruta` es el nombre del archivo o una ruta relativa **dentro de `ALLOWED_INGEST_DIR`**; una absoluta solo vale si cae dentro. Se resuelve con `resolve()` (un enlace simbólico que sale se rechaza) y la pertenencia se comprueba **antes** que la existencia, para no revelar qué hay fuera. Devuelve `indexado <nombre>: N fragmentos`.
- `preguntar_agente(pregunta, session_id="default")`: máximo 8.000 caracteres; `session_id` con `^[A-Za-z0-9_-]{1,64}$`. La memoria vive en RAM mientras el servidor siga activo (no se mezcla con las conversaciones de la web). Si el agente genera un diagrama o unos requisitos, la respuesta menciona el archivo guardado; descargarlo por MCP queda fuera de alcance. Tarda entre unos segundos y un minuto.
- **Errores:** los previstos se lanzan como `ToolError` y el cliente ve su texto con `is_error`; cualquier otra excepción la enmascara el SDK ("Error executing tool X"), así que nuestros `ValueError` se convierten. Un fallo del LLM se devuelve como mensaje genérico.
- Un candado serializa la ingesta y los turnos del agente (almacén y memoria no son seguros ante hilos). Las funciones síncronas se ejecutan en un hilo del SDK, así que una llamada lenta no bloquea el servidor.

Reflexión de diseño (anótala en `docs/09`): exponer `buscar_documentos` permite que el LLM **del cliente** haga su propio razonamiento con tu RAG; `preguntar_agente` entrega un agente completo como caja negra. Ambos tienen sentido; el primero es más barato y componible.

### Transporte
- **stdio** (por defecto): el cliente lanza el proceso. **Nunca imprimir en stdout** (rompe el protocolo); logs a stderr. El modelo de embeddings se carga al primer uso (`LazyEmbedder`), no al arrancar, para no agotar el tiempo de arranque del cliente (`MCP_TIMEOUT`).
- **Directorio de trabajo:** los clientes no garantizan desde qué carpeta lanzan el proceso, y `./data`, `./skills` y `./outputs` son relativas. Al arrancar, `main()` se coloca en la raíz del proyecto si es un checkout (hay `pyproject.toml`); con rutas absolutas en `.env` o en `env` del cliente no cambia nada.
- **HTTP** (opcional, después): para acceso remoto, con autenticación.

### Configuración de clientes
**Claude Code** (las opciones `--env/-e`, `--transport` y `--scope` van **antes** de `--`; entre `--env` y el nombre debe haber otra opción):
```bash
claude mcp add --transport stdio techdoc -- /ruta/al/proyecto/.venv/bin/python -m techdoc_agent.mcp_server
claude mcp list          # estado de los servidores; dentro de una sesión: /mcp
claude mcp remove techdoc
```
El servidor se sitúa solo en `backend/` (donde está `pyproject.toml`), así que encuentra `./data` y `./skills` aunque el cliente lo lance desde otra carpeta. Con rutas de datos propias: `claude mcp add --env DATA_DIR=/ruta/data --transport stdio techdoc -- …`. `MCP_TIMEOUT` (arranque) y `MCP_TOOL_TIMEOUT` (herramienta) se ajustan al lanzar `claude`; conviene subir el segundo si usas `preguntar_agente`.

**Claude Desktop** (macOS y Windows; `claude_desktop_config.json`, rutas **absolutas**, reiniciar la aplicación):
```json
{
  "mcpServers": {
    "techdoc": {
      "command": "/ruta/al/proyecto/.venv/bin/python",
      "args": ["-m", "techdoc_agent.mcp_server"],
      "env": {"DATA_DIR": "/ruta/al/proyecto/backend/data"}
    }
  }
}
```
Sintaxis verificada en la documentación vigente de Claude Code y de MCP (octubre de 2026).

### Pruebas
- Tests automáticos: `tests/test_mcp_server.py` instancia el servidor con un núcleo falso y llama a las cuatro herramientas con `mcp.client.Client`; `tests/test_mcp_stdio.py` lo lanza como subproceso real por stdio (cualquier byte extra en stdout rompería el protocolo).
- Prueba con Claude Code sin tocar tu configuración: `claude -p "lista mis documentos" --mcp-config config.json --strict-mcp-config --allowedTools "mcp__techdoc"`, con un `config.json` que declare el servidor. Prueba manual: el inspector de MCP (`npx @modelcontextprotocol/inspector`) o `claude mcp add` y pedir "lista mis documentos".

### Seguridad MCP
- `ingestar_documento` solo acepta rutas dentro de `ALLOWED_INGEST_DIR` (el error indica que basta el nombre del archivo, sin revelar rutas ajenas).
- Describir bien cada herramienta (es lo que el cliente lee para decidir).
- Tratar los argumentos como no confiables, igual que en la web.

## C. Interfaz web (`frontend/`, Fase 9.B, ADR-026)

Aplicación **Next.js** (App Router, TypeScript estricto, `pnpm`) que solo habla con la API. Se arranca en otra terminal:
```bash
cd frontend
pnpm install
cp .env.example .env.local      # NEXT_PUBLIC_API_URL (por defecto http://127.0.0.1:8000)
pnpm dev                        # http://localhost:3000 (su origen debe estar en CORS_ORIGINS del backend)
```

### Pantalla
- **Izquierda:** conversaciones guardadas (abrir, quitar con confirmación; la actual se marca) y documentos (subir con clic o arrastrando, lista con fragmentos, quitar con confirmación). Los errores del backend (413, 415, 400) se muestran tal cual en un *toast*.
- **Centro:** chat. Progreso en vivo (en cola, pensando, cada herramienta con su resumen y sus ms), respuesta en Markdown con botón **Copiar** en los bloques de código, y artefactos con vista previa (diagrama Mermaid dibujado o requisitos en Markdown) y botón **Descargar**. Enter envía, Shift+Enter añade una línea, máximo 8.000 caracteres.
- **Pasos del agente** (ocultos a primera vista; se abren en un panel lateral con el botón «Pasos del agente» de la cabecera, en todas las anchuras): herramienta, argumentos desplegables, duración, error y tokens de cada respuesta.
- **Selector de modelo** (dentro del compositor, abajo a la izquierda; el contador de caracteres, siempre visible, abajo a la derecha): Claude o Gemini, cada uno con el modelo de `.env`. Los no disponibles salen deshabilitados con su motivo; se bloquea durante un turno; la conversación recuerda el último y una nueva vuelve al de por defecto. Cada respuesta indica «Respondió Gemini · gemini-3.5-flash-lite» (con el logo del proveedor junto al nombre, también en el selector; trazados de Simple Icons, CC0) y el panel de pasos muestra el proveedor de cada respuesta.
- **Cabecera:** estado de la API (`/healthz`), nueva conversación, menú **Apariencia** (ADR-029) y botón de los pasos del agente. En pantallas pequeñas el lateral de conversaciones y documentos también se abre como panel deslizante.
- **La conversación vive en la URL** (`/c/<id>`): recargar o compartir el enlace la reabre desde el servidor. `/` es una conversación nueva; al enviar el primer mensaje se genera el id (32 hex, válido para `session_id`) y la URL cambia sin perder el turno en curso.

### Organización
| Carpeta | Qué hay |
|---|---|
| `src/app/` | Rutas: `layout.tsx` (proveedores y armazón), `page.tsx` (nueva), `c/[id]/page.tsx` (guardada) |
| `src/components/ui/` | Componentes de **shadcn/ui** (se copian al repo y se pueden editar) |
| `src/components/` | Armazón (2 columnas y panel de pasos), proveedores, menú de apariencia, estado de la API, diálogo de confirmación |
| `src/features/` | Una carpeta por funcionalidad: `chat/`, `documents/`, `conversations/`, `trace/` |
| `src/lib/api/` | `schemas.ts` (Zod de cada respuesta y evento SSE), `client.ts` (`fetch` + `ApiError`), `sse.ts` (lector SSE sobre POST), `queries.ts` (hooks de TanStack Query) |
| `src/hooks/` | `use-chat-stream` (envía y vuelca el progreso en el store), `use-copy-to-clipboard` |
| `src/stores/` | Zustand: `chat-store` (conversación en pantalla, turno en curso, progreso), `ui-store` (paneles en móvil) y `appearance-store` (estilo, tinte y fuente) |
| `src/lib/appearance.ts` | Valores permitidos de la apariencia, su schema Zod y el script antes de pintar |
| `src/env.ts` | `NEXT_PUBLIC_API_URL` validada con Zod |

### Dos tipos de estado
- **Del servidor** (documentos, conversaciones, salud, artefactos): **TanStack Query**. Caché, estados de carga y error, y las mutaciones invalidan las listas afectadas.
- **De la interfaz** (qué conversación está en pantalla, si hay un turno en curso, el progreso, los paneles): **Zustand**. El turno escribe en el store y no en el estado del componente, así sobrevive al cambio de `/` a `/c/<id>`; los eventos de una conversación que ya no está en pantalla se descartan.
- **Zod en el borde:** toda respuesta se valida antes de usarse. Si el backend cambia de forma, el error es «La API devolvió una respuesta inesperada» y no un `undefined` en la vista. Los campos que faltan en transcripciones antiguas (`artifacts`, `truncated`) tienen valor por defecto.

### Seguridad
- La salida del modelo nunca entra como HTML: `react-markdown` crea elementos de React y `rehype-sanitize` quita scripts, manejadores `on*` y URLs `javascript:`. Los enlaces se abren con `target="_blank" rel="noopener noreferrer"`.
- Mermaid con `securityLevel: "strict"`; solo su SVG se inserta. Se carga bajo demanda y solo en el navegador.
- Sin CDN: todo (fuentes incluidas) se sirve desde el propio origen. CSP en `next.config.ts` con `connect-src` limitado a la API. Lleva `'unsafe-inline'` en scripts porque el arranque de Next lo exige sin nonces; la defensa principal es lo anterior.
- Llamadas directas a la API con CORS (no por el proxy de Next, que puede retener el SSE en búfer).

### Accesibilidad y revisión de interfaz (ADR-027)
- **Contraste medido** (texto pequeño ≥ 4,5:1, WCAG 1.4.3) en claro y oscuro: texto secundario, botón destructivo, error del chat, badge sin conexión y avisos. Los tokens `--muted-foreground` y `--destructive` (claro), `--success` y los colores de los avisos de sonner se ajustaron para cumplirlo.
- **Teclado:** todo control tiene foco visible; el de la zona de subida (input invisible) se pinta en la zona con `has-[:focus-visible]`.
- **Movimiento reducido:** con `prefers-reduced-motion: reduce` los paneles, diálogos y tooltips solo aparecen con un fundido y los indicadores de carga no giran (`globals.css`).
- **Lectores de pantalla:** la conversación es una región `role="log"` siempre montada, así se anuncian los mensajes y los pasos del agente; el diagrama se nombra con su título; los avisos se llaman «Avisos» y su botón «Cerrar aviso».
- **Textos:** los errores dicen qué hacer; los avisos de error no desaparecen solos (WCAG 2.2.1); los diálogos nombran el objeto («¿Quitar «X» del índice?») y el botón es verbo + objeto.
- **Lectura:** el texto de las respuestas se limita a ~70 caracteres por línea; los nombres de documento no se truncan; ms y tokens con cifras tabulares.

### Pruebas
```bash
pnpm lint && pnpm typecheck
pnpm test        # Vitest + Testing Library + MSW (src/**/*.test.ts[x])
pnpm e2e         # Playwright: levanta backend/tests/e2e_server.py y el frontend con `next dev`
```
El E2E usa la `create_app` real con un **LLM falso guionizado** (sin tokens) y el embedder de hash de los tests, en una carpeta temporal y con puertos propios (8001 y 3100). El frontend corre en modo desarrollo porque React solo avisa de los desajustes de hidratación ahí, y se borra `.next-e2e` en cada ejecución porque la caché de Turbopack llegó a servir CSS antiguo. Hay recorridos en modo oscuro y con movimiento reducido, y una matriz de los 4 temas (Claro, Oscuro, Glass blanca y negra) mide el contraste real de los pares críticos (`e2e/contrast.ts`, que en Glass mide también sobre las manchas del fondo y se queda con el peor). La primera vez hay que instalar el navegador: `pnpm exec playwright install --only-shell chromium`.
