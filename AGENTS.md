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
| Endpoints FastAPI, interfaz web, herramientas MCP, configuración de clientes MCP | `docs/06-api-y-mcp.md` |
| Métricas de evaluación, formato del dataset, cómo se ejecuta el runner | `docs/07-evaluaciones.md` |
| **Fases, entregables, criterios de aceptación y prompts por fase** | `docs/08-roadmap-fases.md` |
| Decisiones tomadas (ADR), tabla de experimentos, fallos encontrados, glosario | `docs/09-decisiones-y-glosario.md` |

### B. Código fuente (`src/techdoc_agent/`)

| Si necesitas… | Está en… | Se crea en |
|---|---|---|
| Variables de entorno / configuración | `src/techdoc_agent/config.py` | Fase 0 |
| Logging JSONL | `src/techdoc_agent/logging_setup.py` | Fase 0 |
| Cliente LLM (`LLMClient`, CLI de Claude Code) y protocolo JSON de herramientas | `src/techdoc_agent/core/llm.py` | Fase 1 |
| Bucle del agente | `src/techdoc_agent/core/agent.py` | Fase 1 |
| Registro y despacho de herramientas | `src/techdoc_agent/core/tools.py` | Fase 1 |
| Historial por sesión | `src/techdoc_agent/core/memory.py` | Fase 1 |
| Resumen de turnos antiguos (recorte de memoria) | `src/techdoc_agent/core/summarizer.py` | tras Fase 3 (ADR-011) |
| Transcripciones de conversaciones y archivos JSON por sesión | `src/techdoc_agent/core/transcripts.py`, `core/storage.py` | Fase 5 (ADR-015) |
| Construcción del system prompt | `src/techdoc_agent/core/prompts.py` | Fase 3 |
| Carga de skills | `src/techdoc_agent/core/skills.py` | Fase 3 |
| Lectura de archivos (.md/.txt/.pdf/código) | `src/techdoc_agent/rag/loaders.py` | Fase 2 |
| Chunking | `src/techdoc_agent/rag/chunking.py` | Fase 2 |
| Embeddings (`Embedder`) | `src/techdoc_agent/rag/embeddings.py` | Fase 2 |
| Interfaz `VectorStore`, `Chunk`, `SearchHit` | `src/techdoc_agent/rag/store.py` | Fase 2 |
| Almacén JSON + numpy | `src/techdoc_agent/rag/store_json.py` | Fase 2 |
| Almacén ChromaDB | `src/techdoc_agent/rag/store_chroma.py` | Fase 4 |
| Selección del almacén (`VECTOR_STORE`) | `src/techdoc_agent/rag/factory.py` | Fase 4 |
| Orquestación de la ingesta y script de consola | `src/techdoc_agent/rag/ingest.py` | Fase 2 |
| Recuperación (consulta de texto → fragmentos; modos `vector`, `lexical`, `hybrid`) | `src/techdoc_agent/rag/retrieval.py` | Fase 2 (modos: 7.B) |
| BM25 hecho a mano (tokenización y puntuación) | `src/techdoc_agent/rag/lexical.py` | Fase 7.B |
| Fusión de rankings RRF | `src/techdoc_agent/rag/hybrid.py` | Fase 7.B |
| Herramientas `buscar_documentos` y `listar_documentos` (registro) | `src/techdoc_agent/core/tools_rag.py` | Fase 3 |
| Herramientas `generar_diagrama` y `generar_requisitos` (registro) | `src/techdoc_agent/core/tools_outputs.py` | Fase 3b |
| Validación y guardado de Mermaid | `src/techdoc_agent/outputs/diagrams.py` | Fase 3b |
| Nombres de archivo generados (slug + id) | `src/techdoc_agent/outputs/naming.py` | Fase 3b |
| Validación y render de requisitos | `src/techdoc_agent/outputs/requirements_doc.py` | Fase 3b |
| Archivos guardados por las herramientas de salida en un turno (API y evals) | `src/techdoc_agent/outputs/artifacts.py` | Fase 7 |
| API web (endpoints) | `src/techdoc_agent/api/main.py` | Fase 5 |
| Interfaz HTML/JS/CSS | `src/techdoc_agent/api/static/` (`index.html`, `app.js`, `app.css`) | Fase 5 |
| Ensamblado del agente (CLI y API) | `src/techdoc_agent/bootstrap.py` | Fase 5 |
| Servidor MCP | `src/techdoc_agent/mcp_server.py` | Fase 6 |
| Chat por consola | `src/techdoc_agent/cli.py` | Fase 1 |

### C. Contenido que el agente usa en ejecución

| Qué | Dónde | Notas |
|---|---|---|
| **Skill del agente** (método y formatos de salida) | `skills/documentacion-tecnica/SKILL.md` | Se inserta en el system prompt. Cambiar el comportamiento del agente = editar este archivo. **No** es documentación del proyecto. |
| Skill activa | variable `ACTIVE_SKILL` en `.env` | |
| Documentos de ejemplo para probar el RAG | `data/sample_docs/taskflow.md` | Documentación ficticia, versionada en git |
| Documentos subidos por el usuario | `data/documents/` | En `.gitignore`; nombres saneados por el sistema (ADR-014) |
| Conversaciones guardadas (web) | `data/conversations/` | En `.gitignore`; contienen texto de las conversaciones |
| Índice vectorial | `data/index/` (`index.json` + `vectors.npy`, o `chroma/`) | En `.gitignore` |
| Artefactos generados (diagramas `.mmd`, requisitos `.md`) | `outputs/` | En `.gitignore`; nombres generados (slug + id) |
| Logs del agente | `logs/agent-YYYYMMDD.jsonl` | En `.gitignore` |

### D. Pruebas y evaluaciones

| Qué | Dónde |
|---|---|
| Tests unitarios y de integración | `tests/` (reflejan la estructura de `src/techdoc_agent/`, p. ej. `tests/rag/test_chunking.py`) |
| Casos de evaluación de ejemplo | `evals/dataset.example.jsonl` |
| Dataset de evaluación real (Fase 7) | `evals/dataset.jsonl` |
| Documentos auxiliares de evaluación (p. ej. documento envenenado) | `evals/fixtures/` |
| Runner de evaluación (`--workers`, `--repeat`, `--only`, `--label`) | `evals/run.py` (Fase 7) |
| Formato y validación del dataset | `evals/dataset.py` (Fase 7) |
| Reglas de evaluación (pasa/falla por métrica) | `evals/rules.py` (Fase 7) |
| Comparación de modos de búsqueda sin LLM (hit@k, MRR) | `evals/retrieval.py` (Fase 7.B) |
| Resultados de ejecuciones | `evals/results/` (en `.gitignore`) |

### E. Configuración y raíz

| Qué | Dónde |
|---|---|
| Plantilla de variables de entorno | `.env.example` (el `.env` real no se versiona ni se lee/imprime) |
| Dependencias | `requirements.txt` |
| Empaquetado del proyecto | `pyproject.toml` (Fase 0) |
| Reglas de git | `.gitignore` |
| Presentación del proyecto | `README.md` |
| Este archivo (reglas para agentes) | `AGENTS.md` (`CLAUDE.md` solo lo importa) |

### Dónde poner cosas nuevas

| Si vas a crear… | Ponlo en… |
|---|---|
| Una herramienta nueva del agente | Función en `core/` u `outputs/` + registro en `core/tools.py` + schema documentado en `docs/04` + caso en `evals/` |
| Un loader de un formato nuevo | `rag/loaders.py` + extensión en `ALLOWED_EXTENSIONS` (`.env.example`) + test |
| Otro almacén vectorial | `rag/store_<nombre>.py` implementando `VectorStore` + tests parametrizados |
| Un endpoint | `api/main.py` (solo adaptación; la lógica va al núcleo) |
| Una herramienta MCP | `mcp_server.py` (solo adaptación; la lógica va al núcleo) |
| Otra skill | `skills/<nombre>/SKILL.md` |
| Una decisión de diseño | Entrada nueva en `docs/09-decisiones-y-glosario.md` |
| Un fallo reproducible | Fila en la tabla de fallos de `docs/09` + caso en `evals/dataset.jsonl` |
| Una variable de configuración | `config.py` + `.env.example` + mención en el doc afectado |

### Evita estas confusiones
- **"Documentos"** puede significar tres cosas distintas:
  1. `docs/` → documentación **del proyecto** (para desarrolladores).
  2. `data/sample_docs/` y `data/documents/` → documentos que el agente **indexa** (conocimiento del RAG).
  3. `skills/` → instrucciones que el agente **carga** (comportamiento).
  Ante la duda, pregunta cuál se pretende.
- **Skill ≠ conocimiento.** La skill dice *cómo* trabajar; el conocimiento vive en los documentos indexados.
- **`outputs/` (carpeta raíz)** son artefactos que genera el agente; **`src/techdoc_agent/outputs/`** es el código que los valida y guarda. No mezclar.
- Los **nombres de herramientas** (`buscar_documentos`, …) y sus schemas se definen en `docs/04`; el código debe coincidir con ese documento (si cambia uno, actualizar el otro).

---

## Forma de trabajar (importante)
- El autor está aprendiendo. **Antes de cada fase**, explica en 3-5 líneas qué vas a construir y por qué. **Al terminarla**, resume los conceptos clave en 3-5 líneas.
- Trabaja **una fase a la vez**. No adelantes código de fases posteriores. Al terminar, ejecuta los criterios de aceptación de la fase y reporta cuáles pasan.
- Pide confirmación antes de añadir dependencias que no estén en `requirements.txt`.
- Si una decisión de diseño cambia respecto a la documentación, **actualiza el doc correspondiente** y añade una entrada en `docs/09-decisiones-y-glosario.md`.
- Pasos pequeños, commits pequeños. Mensajes en **Conventional Commits** con descripción en español e imperativo: `tipo(ámbito): descripción` (p. ej. `feat(core): añade bucle del agente`). Tipos: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `build`.
- **No hacer commits por iniciativa propia.** Al terminar una fase, proponer los commits en una tabla (hash o mensaje + nº de archivos) y esperar a que el autor lo pida. Tampoco `git push` sin que lo pida.
- Antes de usar una API de una librería (CLI de Claude Code, chromadb, mcp, fastapi, sentence-transformers), **verifica en su documentación vigente** los nombres exactos; no te fíes de la memoria.

## Reglas de arquitectura (no negociables)
1. **Sin frameworks de agentes** (nada de LangChain, LangGraph, LlamaIndex, CrewAI, etc.). El LLM se invoca con el CLI de Claude Code en modo no interactivo (`claude -p`, sin API key) detrás de una interfaz `LLMClient`, y el bucle del agente se escribe a mano (ver ADR-008).
2. **Núcleo + adaptadores.** `core/` y `rag/` no importan nada de `api/` ni de `mcp_server.py`. FastAPI y MCP son adaptadores delgados que llaman al núcleo.
3. **El almacén vectorial va detrás de una interfaz** (`VectorStore`). Primero JSON + numpy, luego ChromaDB; el agente no debe notar el cambio.
4. **El agente decide.** Nunca se hace una búsqueda automática antes de llamar al LLM.
5. **Los documentos indexados son datos no confiables.** Su contenido nunca se trata como instrucciones (ver `docs/04-diseno-agente.md`, sección Seguridad).
6. **Todo paso del agente se registra** (mensaje, herramienta, argumentos, resultado, tokens, duración) en `logs/` en formato JSONL.
7. Límites duros: máximo de iteraciones del bucle, tiempo máximo por llamada al LLM (`LLM_TIMEOUT_S`), tamaño máximo de archivo subido, tipos de archivo permitidos.

## Stack
- Python 3.11+
- CLI `claude` (Claude Code) como LLM — modelo configurable por `LLM_MODEL` (por defecto `claude-haiku-5-5`)
- `numpy` + `sentence-transformers` (embeddings locales, multilingüe) → luego `chromadb`
- `fastapi` + `uvicorn` + HTML/JS puro (sin framework de frontend)
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
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # y comprobar que `claude` está instalado y con sesión iniciada

pytest                                                   # tests
python -m techdoc_agent.cli                              # chat por consola (/ingestar <ruta>, /nuevo, /salir)
uvicorn techdoc_agent.api.main:app --reload              # web (Fase 5)
python -m techdoc_agent.mcp_server                       # MCP por stdio (Fase 6)
python -m evals.run                                      # evaluaciones (Fase 7)
```

## Estructura objetivo
```
AGENTS.md  CLAUDE.md  README.md  requirements.txt  pyproject.toml  .env.example
docs/                  # documentación del proyecto (01-09)
skills/documentacion-tecnica/SKILL.md
src/techdoc_agent/
  config.py  logging_setup.py  bootstrap.py  cli.py  mcp_server.py
  core/      agent.py  tools.py  tools_rag.py  tools_outputs.py  prompts.py  skills.py
             memory.py  summarizer.py  transcripts.py  storage.py  llm.py
  rag/       loaders.py  chunking.py  embeddings.py  store.py  retrieval.py  lexical.py  hybrid.py
             store_json.py  store_chroma.py  factory.py  ingest.py
  outputs/   diagrams.py  requirements_doc.py  naming.py  artifacts.py
  api/       main.py  static/index.html  static/app.js  static/app.css
tests/
evals/       dataset.example.jsonl  dataset.jsonl  dataset.py  rules.py  run.py  retrieval.py  fixtures/  results/
data/        sample_docs/  documents/  index/  conversations/
outputs/     # artefactos generados (runtime)
logs/        # JSONL (runtime)
```

## Definición de "terminado" para cualquier fase
- Los criterios de aceptación de la fase en `docs/08-roadmap-fases.md` pasan.
- Hay tests para la lógica nueva.
- El README o el doc afectado está actualizado.
- Nada de secretos ni datos locales en git.
