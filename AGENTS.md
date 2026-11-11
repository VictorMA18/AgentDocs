# TechDoc Agent — instrucciones para agentes de código

Agente que indexa documentación técnica (de una librería o de un proyecto de software) y, a partir de ella, responde con ejemplos de código y genera **diagramas** (Mermaid) y **requisitos** (Markdown estructurado). El RAG es una **herramienta** que el agente decide usar, no un paso fijo.

Este proyecto es de **aprendizaje y portafolio**. El objetivo no es solo que funcione, sino que el autor entienda cada pieza y pueda explicarla.

## Lee primero
1. `docs/01-vision-y-alcance.md`
2. `docs/03-arquitectura.md`
3. `docs/08-roadmap-fases.md` ← **trabaja siguiendo las fases, en orden**

---

## Mapa de ubicaciones (dónde buscar cada cosa)

**Regla:** antes de buscar con Grep/Glob por todo el repo, consulta esta tabla. Si algo no está donde se indica, aún puede no existir (se crea en la fase señalada); no lo inventes ni lo asumas: dilo y pregunta.

### A. Documentación del proyecto (`docs/`) — para quien desarrolla

| Si necesitas… | Está en… |
|---|---|
| Qué es el proyecto, alcance, qué NO hacer, criterio de éxito | `docs/01-vision-y-alcance.md` |
| Requisitos funcionales (RF-xx) y no funcionales (RNF-xx) con criterios de aceptación | `docs/02-requisitos.md` |
| Componentes, flujos, diagramas, datos en disco, decisiones de diseño clave | `docs/03-arquitectura.md` |
| Bucle del agente, **schemas JSON de las herramientas**, estructura del system prompt, memoria, **seguridad**, formato de logs | `docs/04-diseno-agente.md` |
| Ingesta, loaders, chunking, interfaz `Embedder`, interfaz `VectorStore`, JSON/Chroma, recuperación | `docs/05-rag.md` |
| Endpoints FastAPI, frontend Next.js (sección C), herramientas MCP, configuración de clientes MCP | `docs/06-api-y-mcp.md` |
| Métricas de evaluación, formato del dataset, cómo se ejecuta el runner | `docs/07-evaluaciones.md` |
| **Fases, entregables, criterios de aceptación y prompts por fase** | `docs/08-roadmap-fases.md` |
| Decisiones tomadas (ADR), tabla de experimentos, fallos encontrados, glosario | `docs/09-decisiones-y-glosario.md` |

### B. Código fuente (`backend/src/techdoc_agent/`)

| Si necesitas… | Está en… | Se crea en |
|---|---|---|
| Variables de entorno / configuración | `backend/src/techdoc_agent/config.py` | Fase 0 |
| Logging JSONL | `backend/src/techdoc_agent/logging_setup.py` | Fase 0 |
| Cliente LLM (`LLMClient`, CLI de Claude Code) y protocolo JSON de herramientas | `backend/src/techdoc_agent/core/llm.py` | Fase 1 |
| Cliente de la API de Gemini (proveedor alternativo) | `backend/src/techdoc_agent/core/llm_gemini.py` | ADR-024 |
| Elección del proveedor (`LLM_PROVIDER`: `claude` o `gemini`) | `backend/src/techdoc_agent/core/llm_factory.py` | ADR-024 |
| Bucle del agente | `backend/src/techdoc_agent/core/agent.py` | Fase 1 |
| Registro y despacho de herramientas | `backend/src/techdoc_agent/core/tools.py` | Fase 1 |
| Historial por sesión | `backend/src/techdoc_agent/core/memory.py` | Fase 1 |
| Resumen de turnos antiguos (recorte de memoria) | `backend/src/techdoc_agent/core/summarizer.py` | tras Fase 3 (ADR-011) |
| Transcripciones de conversaciones y archivos JSON por sesión | `backend/src/techdoc_agent/core/transcripts.py`, `core/storage.py` | Fase 5 (ADR-015) |
| Construcción del system prompt | `backend/src/techdoc_agent/core/prompts.py` | Fase 3 |
| Carga de skills (y de sus guías `guias/*.md`) | `backend/src/techdoc_agent/core/skills.py` | Fase 3 (guías: 8) |
| Herramienta `cargar_guia` (divulgación progresiva de la skill) | `backend/src/techdoc_agent/core/tools_skill.py` | Fase 8 |
| Lectura de archivos (.md/.txt/.pdf/código) | `backend/src/techdoc_agent/rag/loaders.py` | Fase 2 |
| Chunking | `backend/src/techdoc_agent/rag/chunking.py` | Fase 2 |
| Embeddings (`Embedder`) | `backend/src/techdoc_agent/rag/embeddings.py` | Fase 2 |
| Interfaz `VectorStore`, `Chunk`, `SearchHit` | `backend/src/techdoc_agent/rag/store.py` | Fase 2 |
| Almacén JSON + numpy | `backend/src/techdoc_agent/rag/store_json.py` | Fase 2 |
| Almacén ChromaDB | `backend/src/techdoc_agent/rag/store_chroma.py` | Fase 4 |
| Selección del almacén (`VECTOR_STORE`) | `backend/src/techdoc_agent/rag/factory.py` | Fase 4 |
| Orquestación de la ingesta y script de consola | `backend/src/techdoc_agent/rag/ingest.py` | Fase 2 |
| Recuperación (consulta de texto → fragmentos; modos `vector`, `lexical`, `hybrid`) | `backend/src/techdoc_agent/rag/retrieval.py` | Fase 2 (modos: 7.B) |
| BM25 hecho a mano (tokenización y puntuación) | `backend/src/techdoc_agent/rag/lexical.py` | Fase 7.B |
| Fusión de rankings RRF | `backend/src/techdoc_agent/rag/hybrid.py` | Fase 7.B |
| Herramientas `buscar_documentos` y `listar_documentos` (registro) | `backend/src/techdoc_agent/core/tools_rag.py` | Fase 3 |
| Herramientas `generar_diagrama` y `generar_requisitos` (registro) | `backend/src/techdoc_agent/core/tools_outputs.py` | Fase 3b |
| Validación y guardado de Mermaid | `backend/src/techdoc_agent/outputs/diagrams.py` | Fase 3b |
| Validación real de Mermaid con `mmdc` (opcional, `MERMAID_VALIDATE=cli`) | `backend/src/techdoc_agent/outputs/mermaid_cli.py` y `backend/tools/mermaid/` | Fase 8 |
| Nombres de archivo generados (slug + id) | `backend/src/techdoc_agent/outputs/naming.py` | Fase 3b |
| Validación y render de requisitos | `backend/src/techdoc_agent/outputs/requirements_doc.py` | Fase 3b |
| Archivos guardados por las herramientas de salida en un turno (API y evals) | `backend/src/techdoc_agent/outputs/artifacts.py` | Fase 7 |
| API web: punto de entrada (`app`) | `backend/src/techdoc_agent/api/main.py` | Fase 5 |
| API web: ensamblado (middleware, CORS, routers) | `backend/src/techdoc_agent/api/app.py` | Fase 9 (ADR-025) |
| API web: endpoints por recurso (chat, conversaciones, documentos, artefactos, salud) | `backend/src/techdoc_agent/api/routers/` | Fase 9 |
| API web: núcleo compartido (`Core`, `get_core`), modelos de entrada y frontera de seguridad | `backend/src/techdoc_agent/api/deps.py`, `schemas.py`, `security.py` | Fase 9 |
| Ensamblado del agente (CLI y API) | `backend/src/techdoc_agent/bootstrap.py` | Fase 5 |
| Servidor MCP | `backend/src/techdoc_agent/mcp_server.py` | Fase 6 |
| Chat por consola | `backend/src/techdoc_agent/cli.py` | Fase 1 |

### B2. Frontend (`frontend/`, Next.js — Fase 9.B, ADR-026)

| Si necesitas… | Está en… |
|---|---|
| Rutas: armazón y proveedores, conversación nueva, conversación guardada (`/c/<id>`) | `frontend/src/app/layout.tsx`, `page.tsx`, `c/[id]/page.tsx` |
| Componentes de shadcn/ui (generados con `pnpm dlx shadcn add`, editables) | `frontend/src/components/ui/` |
| Armazón de 3 columnas, proveedores (Query, tema, toasts), modo oscuro, estado de la API, confirmación | `frontend/src/components/` |
| Chat: vista, mensajes, compositor, progreso, Markdown seguro, Mermaid, artefactos | `frontend/src/features/chat/` |
| Documentos (subir, listar, quitar) · conversaciones · pasos del agente | `frontend/src/features/documents/`, `conversations/`, `trace/` |
| **Schemas Zod** de cada respuesta y evento SSE (contrato con la API) | `frontend/src/lib/api/schemas.ts` |
| Cliente HTTP (`ApiError`), lector SSE sobre POST, hooks de TanStack Query | `frontend/src/lib/api/client.ts`, `sse.ts`, `queries.ts` |
| Hook del chat (envía y vuelca el progreso en el store) | `frontend/src/hooks/use-chat-stream.ts` |
| Stores de Zustand (chat en pantalla, paneles) | `frontend/src/stores/` |
| Variable `NEXT_PUBLIC_API_URL` validada · CSP y cabeceras | `frontend/src/env.ts` · `frontend/next.config.ts` |
| Tests unitarios (junto al código) · utilidades de test (MSW) · E2E | `frontend/src/**/*.test.ts[x]` · `frontend/src/test/` · `frontend/e2e/` |
| Servidor de la API para el E2E (núcleo real, LLM guionizado) | `backend/tests/e2e_server.py` |

### C. Contenido que el agente usa en ejecución

| Qué | Dónde | Notas |
|---|---|---|
| **Skill del agente** (método general y guías de diagramas y requisitos) | `backend/skills/documentacion-tecnica/SKILL.md` y `backend/skills/documentacion-tecnica/guias/*.md` | Se inserta en el system prompt. Cambiar el comportamiento del agente = editar este archivo. **No** es documentación del proyecto. |
| Skill activa | variable `ACTIVE_SKILL` en `.env` | |
| Documentos de ejemplo para probar el RAG | `backend/data/sample_docs/taskflow.md` | Documentación ficticia, versionada en git |
| Documentos subidos por el usuario | `backend/data/documents/` | En `.gitignore`; nombres saneados por el sistema (ADR-014) |
| Conversaciones guardadas (web) | `backend/data/conversations/` | En `.gitignore`; contienen texto de las conversaciones |
| Índice vectorial | `backend/data/index/` (`index.json` + `vectors.npy`, o `chroma/`) | En `.gitignore` |
| Artefactos generados (diagramas `.mmd`, requisitos `.md`) | `backend/outputs/` | En `.gitignore`; nombres generados (slug + id) |
| Logs del agente | `backend/logs/agent-YYYYMMDD.jsonl` | En `.gitignore` |

### D. Pruebas y evaluaciones

| Qué | Dónde |
|---|---|
| Tests unitarios y de integración | `backend/tests/` (reflejan la estructura de `backend/src/techdoc_agent/`, p. ej. `backend/tests/rag/test_chunking.py`) |
| Casos de evaluación de ejemplo | `backend/evals/dataset.example.jsonl` |
| Dataset de evaluación real (Fase 7) | `backend/evals/dataset.jsonl` |
| Documentos auxiliares de evaluación (p. ej. documento envenenado) | `backend/evals/fixtures/` |
| Runner de evaluación (`--workers`, `--repeat`, `--only`, `--label`) | `backend/evals/run.py` (Fase 7) |
| Formato y validación del dataset | `backend/evals/dataset.py` (Fase 7) |
| Reglas de evaluación (pasa/falla por métrica) | `backend/evals/rules.py` (Fase 7) |
| Comparación de modos de búsqueda sin LLM (hit@k, MRR) | `backend/evals/retrieval.py` (Fase 7.B) |
| Resultados de ejecuciones | `backend/evals/results/` (en `.gitignore`) |

### E. Configuración y raíz

| Qué | Dónde |
|---|---|
| Plantilla de variables de entorno | `backend/.env.example` (el `.env` real no se versiona ni se lee/imprime) · `frontend/.env.example` (se copia a `.env.local`) |
| Dependencias | `backend/requirements.txt` · `frontend/package.json` (+ `pnpm-lock.yaml`) |
| Empaquetado del proyecto | `backend/pyproject.toml` (Fase 0) |
| Reglas de git | `.gitignore` |
| Presentación del proyecto | `README.md` |
| Este archivo (reglas para agentes) | `AGENTS.md` (`CLAUDE.md` solo lo importa) |
| Skills de interfaz para el agente de código (`better-*`, `interface-review`) | `.claude/skills/` (fuera de git) · versiones fijadas en `skills-lock.json`; se restauran con `npx skills experimental_install` (ADR-027) |

### Dónde poner cosas nuevas

| Si vas a crear… | Ponlo en… |
|---|---|
| Una herramienta nueva del agente | Función en `core/` u `outputs/` (código) + registro en `core/tools.py` + schema documentado en `docs/04` + caso en `backend/evals/` |
| Un loader de un formato nuevo | `backend/src/techdoc_agent/rag/loaders.py` + extensión en `ALLOWED_EXTENSIONS` (`backend/.env.example`) + test |
| Otro almacén vectorial | `backend/src/techdoc_agent/rag/store_<nombre>.py` implementando `VectorStore` + tests parametrizados |
| Un endpoint | `api/routers/<recurso>.py` + `include_router` en `api/app.py` (solo adaptación; la lógica va al núcleo) + su schema Zod en `frontend/src/lib/api/schemas.ts` si lo usa la interfaz |
| Una llamada a la API desde el frontend | Función en `frontend/src/lib/api/client.ts` (validada con un schema Zod) + hook en `queries.ts` (`useQuery`/`useMutation` con invalidación) |
| Una pantalla o funcionalidad de la interfaz | `frontend/src/features/<funcionalidad>/` (+ test `*.test.tsx` al lado) |
| Un componente de shadcn/ui | `pnpm dlx shadcn@<versión> add <nombre>` desde `frontend/` (queda en `src/components/ui/`) |
| Estado que solo existe en la pantalla | Un store de Zustand en `frontend/src/stores/` (lo que viene del servidor va en TanStack Query, no aquí) |
| Una herramienta MCP | `mcp_server.py` (solo adaptación; la lógica va al núcleo) |
| Otra skill | `backend/skills/<nombre>/SKILL.md` |
| Instrucciones detalladas de una skill que no hace falta en cada llamada | `backend/skills/<nombre>/guias/<guia>.md` (con `description` en el frontmatter; el agente las carga con `cargar_guia`) |
| Una decisión de diseño | Entrada nueva en `docs/09-decisiones-y-glosario.md` |
| Un fallo reproducible | Fila en la tabla de fallos de `docs/09` + caso en `backend/evals/dataset.jsonl` |
| Una variable de configuración | `config.py` + `backend/.env.example` + mención en el doc afectado |

### Evita estas confusiones
- **"Documentos"** puede significar tres cosas distintas:
  1. `docs/` → documentación **del proyecto** (para desarrolladores).
  2. `data/sample_docs/` y `data/documents/` → documentos que el agente **indexa** (conocimiento del RAG).
  3. `skills/` → instrucciones que el agente **carga** (comportamiento).
  Ante la duda, pregunta cuál se pretende.
- **Skill ≠ conocimiento.** La skill dice *cómo* trabajar; el conocimiento vive en los documentos indexados.
- **Dos clases de skills:** `backend/skills/` es la skill **del agente TechDoc** (se inserta en su system prompt). `.claude/skills/` son skills **para el agente de código** que desarrolla el proyecto (revisión de interfaz); el agente TechDoc nunca las carga.
- **`backend/outputs/`** son artefactos que genera el agente; **`backend/src/techdoc_agent/outputs/`** es el código que los valida y guarda. No mezclar.
- Los **nombres de herramientas** (`buscar_documentos`, …) y sus schemas se definen en `docs/04`; el código debe coincidir con ese documento (si cambia uno, actualizar el otro).

---

## Forma de trabajar (importante)
- El autor está aprendiendo. **Antes de cada fase**, explica en 3-5 líneas qué vas a construir y por qué. **Al terminarla**, resume los conceptos clave en 3-5 líneas.
- Trabaja **una fase a la vez**. No adelantes código de fases posteriores. Al terminar, ejecuta los criterios de aceptación de la fase y reporta cuáles pasan.
- Pide confirmación antes de añadir dependencias que no estén en `requirements.txt`.
- Si una decisión de diseño cambia respecto a la documentación, **actualiza el doc correspondiente** y añade una entrada en `docs/09-decisiones-y-glosario.md`.
- Pasos pequeños, commits pequeños. Mensajes en **Conventional Commits** con descripción en español e imperativo: `tipo(ámbito): descripción` (p. ej. `feat(core): añade bucle del agente`). Tipos: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `build`.
- **No hacer commits por iniciativa propia.** Al terminar una fase, proponer los commits en una tabla (hash o mensaje + nº de archivos) y esperar a que el autor lo pida. Tampoco `git push` sin que lo pida.
- Antes de usar una API de una librería (CLI de Claude Code, chromadb, mcp, fastapi, sentence-transformers, Next.js, TanStack Query, Zustand, Zod, shadcn/ui), **verifica en su documentación vigente** los nombres exactos; no te fíes de la memoria. Next.js trae su documentación de la versión instalada en `frontend/node_modules/next/dist/docs/`, y los tipos de cada paquete en `node_modules` son la referencia final (p. ej. MSW 3 renombró `onUnhandledRequest` a `onUnhandledFrame`).

## Reglas de arquitectura (no negociables)
1. **Sin frameworks de agentes** (nada de LangChain, LangGraph, LlamaIndex, CrewAI, etc.). El LLM se invoca con el CLI de Claude Code en modo no interactivo (`claude -p`, sin API key) detrás de una interfaz `LLMClient`, y el bucle del agente se escribe a mano (ver ADR-008).
2. **Núcleo + adaptadores.** `core/` y `rag/` no importan nada de `api/` ni de `mcp_server.py`. FastAPI y MCP son adaptadores delgados que llaman al núcleo. El **frontend solo habla con la API HTTP** (nunca con el núcleo ni con archivos del backend) y valida con Zod todo lo que recibe; la salida del modelo nunca se inserta como HTML.
3. **El almacén vectorial va detrás de una interfaz** (`VectorStore`). Primero JSON + numpy, luego ChromaDB; el agente no debe notar el cambio.
4. **El agente decide.** Nunca se hace una búsqueda automática antes de llamar al LLM.
5. **Los documentos indexados son datos no confiables.** Su contenido nunca se trata como instrucciones (ver `docs/04-diseno-agente.md`, sección Seguridad).
6. **Todo paso del agente se registra** (mensaje, herramienta, argumentos, resultado, tokens, duración) en `logs/` en formato JSONL.
7. Límites duros: máximo de iteraciones del bucle, tiempo máximo por llamada al LLM (`LLM_TIMEOUT_S`), tamaño máximo de archivo subido, tipos de archivo permitidos.

## Stack
- Python 3.11+
- CLI `claude` (Claude Code) como LLM — modelo configurable por `LLM_MODEL` (por defecto `claude-haiku-5-5`)
- Alternativa: API de Gemini con `httpx` (`LLM_PROVIDER=gemini`, `GEMINI_API_KEY`, `GEMINI_MODEL`, por defecto `gemini-3.5-flash-lite`, la que da cuota con el plan gratuito); la clave solo en `.env`, nunca en código, logs ni git
- `numpy` + `sentence-transformers` (embeddings locales, multilingüe) → luego `chromadb`
- `fastapi` + `uvicorn` (API pura; CORS para el frontend con `CORS_ORIGINS`)
- Frontend (`frontend/`, Node 22 + `pnpm`): Next.js 16 (App Router, TypeScript estricto), Tailwind 4, shadcn/ui, TanStack Query 5, Zustand 5, Zod 4, `react-markdown` + `rehype-sanitize`, `mermaid`, `next-themes`, `sonner`; pruebas con Vitest + Testing Library + MSW y Playwright
- `mcp` 2.x (SDK oficial de Python, `MCPServer`; antes `FastMCP`)
- `pytest`

## Convenciones de código
- Type hints en todo; `dataclass` o `pydantic` para estructuras.
- Nombres de código en inglés; **comentarios y docstrings en español**.
- **Nombres de herramientas del agente en español, snake_case** (`buscar_documentos`, etc.): son parte de la API que ve el modelo.
- Los logs en el servidor MCP por stdio van a **stderr**; stdout está reservado al protocolo.
- Configuración solo por variables de entorno (`.env`, ver `.env.example`). Nunca claves en el código.
- Funciones pequeñas, una responsabilidad. Sin abstracciones "por si acaso".

## Comandos
El backend se ejecuta **desde `backend/`** (las rutas `./data`, `./skills`, `./outputs` son relativas a esa carpeta). El `.venv` vive en la raíz.
```bash
python -m venv .venv && source .venv/bin/activate        # en la raíz del repositorio
pip install -r backend/requirements.txt && pip install -e backend/
cd backend && cp .env.example .env                        # y comprobar que `claude` está instalado y con sesión iniciada

pytest                                                   # tests (desde backend/)
python -m techdoc_agent.cli                              # chat por consola (/ingestar <ruta>, /nuevo, /salir)
uvicorn techdoc_agent.api.main:app --reload              # API en http://127.0.0.1:8000
python -m techdoc_agent.mcp_server                       # MCP por stdio (Fase 6)
python -m evals.run                                      # evaluaciones (Fase 7)
```
El frontend se ejecuta **desde `frontend/`**, en otra terminal:
```bash
pnpm install && cp .env.example .env.local               # NEXT_PUBLIC_API_URL (por defecto http://127.0.0.1:8000)
pnpm dev                                                 # http://localhost:3000
pnpm lint && pnpm typecheck && pnpm test                 # ESLint, TypeScript y Vitest
pnpm e2e                                                 # Playwright (levanta backend/tests/e2e_server.py y el frontend)
```

## Estructura objetivo
```
AGENTS.md  CLAUDE.md  README.md  LICENSE  .gitignore
docs/                  # documentación del proyecto (01-09)
backend/
  pyproject.toml  requirements.txt  .env.example
  skills/documentacion-tecnica/SKILL.md  guias/
  tools/mermaid/       # mermaid-cli opcional (package.json); node_modules fuera de git
  src/techdoc_agent/
    config.py  logging_setup.py  bootstrap.py  cli.py  mcp_server.py
    core/      agent.py  tools.py  tools_rag.py  tools_outputs.py  tools_skill.py  prompts.py  skills.py
               memory.py  summarizer.py  transcripts.py  storage.py  llm.py  llm_gemini.py  llm_factory.py
    rag/       loaders.py  chunking.py  embeddings.py  store.py  retrieval.py  lexical.py  hybrid.py
               store_json.py  store_chroma.py  factory.py  ingest.py
    outputs/   diagrams.py  mermaid_cli.py  requirements_doc.py  naming.py  artifacts.py
    api/       main.py  app.py  deps.py  schemas.py  security.py
               routers/  chat.py  conversations.py  documents.py  artifacts.py  health.py
  tests/
  evals/       dataset.example.jsonl  dataset.jsonl  dataset.py  rules.py  run.py  retrieval.py  fixtures/  results/
  data/        sample_docs/  documents/  index/  conversations/
  outputs/     # artefactos generados (runtime)
  logs/        # JSONL (runtime)
frontend/      # Next.js (Fase 9.B): package.json  next.config.ts  components.json  .env.example
  src/app/  components/ui/  components/  features/{chat,documents,conversations,trace}/
  src/lib/api/  hooks/  stores/  env.ts  test/
  e2e/         # Playwright
```

## Cambios en la interfaz (`frontend/`)
- Antes de dar por terminado un cambio visual, revísalo con las skills de `.claude/skills/` (`better-interface` para una pantalla; el autor lanza `/interface-review` para una rama o PR) y aporta evidencia medida, no opinión.
- Mínimos que ya cubren los E2E: foco visible en todo control, contraste ≥ 4,5:1 en texto pequeño (claro y oscuro), sin movimiento con `prefers-reduced-motion`, errores que no desaparecen solos y dicen qué hacer, nada cortado sin forma de leerlo entero.

## Definición de "terminado" para cualquier fase
- Los criterios de aceptación de la fase en `docs/08-roadmap-fases.md` pasan.
- Hay tests para la lógica nueva.
- El README o el doc afectado está actualizado.
- Nada de secretos ni datos locales en git.
