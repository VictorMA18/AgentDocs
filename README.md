# TechDoc Agent

Agente de documentación técnica: le pasas documentación (de una librería o de tu proyecto) y te responde con ejemplos de código, y puede generar **diagramas** y **requisitos** a partir de ella.

> Proyecto de aprendizaje: construir un agente **desde cero**, sin frameworks de agentes, entendiendo cada pieza.

## Contenido del repositorio

El código se construye por fases siguiendo el roadmap (`docs/08-roadmap-fases.md`).

| Archivo | Para qué sirve |
|---|---|
| `AGENTS.md` | Reglas del proyecto y **mapa de ubicaciones** (dónde está cada cosa) |
| `CLAUDE.md` | Importa `AGENTS.md`; es el archivo que Claude Code lee automáticamente |
| `docs/01` … `docs/09` | Visión, requisitos, arquitectura, diseño del agente, RAG, API/MCP, evaluaciones, roadmap y decisiones |
| `src/techdoc_agent/` | Código del paquete (`config.py`, `logging_setup.py`, …) |
| `tests/` | Tests con `pytest` |
| `skills/documentacion-tecnica/SKILL.md` | La skill que se carga en el agente |
| `evals/dataset.example.jsonl` | Casos de prueba de ejemplo |
| `data/sample_docs/taskflow.md` | Documentación ficticia para probar sin material real |
| `.env.example`, `requirements.txt`, `pyproject.toml` | Configuración base |

## Instalación

Necesitas Python 3.11+ y el CLI `claude` (Claude Code) instalado y con sesión iniciada; no hace falta API key.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install python-dotenv pytest             # dependencias de las Fases 0-1
pip install -e .                             # instala el paquete en modo editable
cp .env.example .env                         # modelo por defecto: claude-haiku-5-5
pytest
```

Las dependencias se instalan por fases (ver ADR-007 en `docs/09`). Para la ingesta y el RAG (Fase 2), instala PyTorch **solo CPU** antes (ADR-009):

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install numpy sentence-transformers pypdf
```

## Chat por consola

```bash
python -m techdoc_agent.cli
```
Al arrancar carga el modelo de embeddings (unos segundos). Comandos: `/ingestar <ruta>` indexa un archivo o carpeta (p. ej. `/ingestar data/sample_docs`), `/nuevo` reinicia la conversación y `/salir` termina. El agente tiene dos herramientas, `buscar_documentos` y `listar_documentos`, y decide cuándo usarlas según el system prompt (reglas fijas + `skills/documentacion-tecnica/SKILL.md`; editar la skill cambia su comportamiento sin tocar código). Prueba: *"hola"* (sin búsqueda), *"¿Cuál es la concurrencia por defecto del worker?"* (una búsqueda y cita). Para conversaciones largas, la memoria resume los turnos antiguos (`MEMORY_MAX_TOKENS`, `MEMORY_KEEP_TURNS` en `.env`) y conserva los últimos íntegros. Para diagramas y requisitos, el agente usa `generar_diagrama` y `generar_requisitos`: validan lo que escribe el modelo (si hay errores se los devuelven para que se corrija) y guardan el resultado en `outputs/` con un nombre generado (prueba: *"Haz un diagrama de secuencia de encolar y procesar un trabajo"*). Tras cada respuesta se muestran las herramientas usadas, su duración y los tokens.

## Indexar y buscar documentos

```bash
python -m techdoc_agent.rag.ingest data/sample_docs --buscar "reintentos"   # indexa y busca
python -m techdoc_agent.rag.ingest --buscar "reintentos" --top-k 3           # solo busca
```
La primera vez descarga el modelo de embeddings (~470 MB). El índice queda en `data/index/` (`index.json` + `vectors.npy`, ignorado por git).

## Estructura del núcleo (`src/techdoc_agent/core/`)

| Módulo | Responsabilidad |
|---|---|
| `llm.py` | Interfaz `LLMClient` y `ClaudeCliClient` (llama a `claude -p`, protocolo JSON de herramientas) |
| `tools.py` | Registro de herramientas y `dispatch()` que nunca lanza excepciones |
| `memory.py` | Historial por `session_id` |
| `agent.py` | Bucle del agente con tope de iteraciones y logging de cada paso |

## Estructura del RAG (`src/techdoc_agent/rag/`)

| Módulo | Responsabilidad |
|---|---|
| `loaders.py` | Lee `.md .txt .pdf` y código; valida tipo y tamaño |
| `chunking.py` | Divide en fragmentos por secciones, sin partir bloques de código |
| `embeddings.py` | Interfaz `Embedder` y modelo local multilingüe |
| `store.py` / `store_json.py` | Interfaz `VectorStore` y almacén JSON + numpy |
| `ingest.py` / `retrieval.py` | Orquesta la ingesta (y el script de consola) y consulta el índice |

## Configuración y logs

- Toda la configuración se lee de variables de entorno (`.env`) en `techdoc_agent.config.settings`.
- Cada evento del agente se registra como una línea JSON en `logs/agent-YYYYMMDD.jsonl` con `techdoc_agent.logging_setup.log_event(...)`.

## Estado

Fases 0, 1 y 2 completadas. Ver el checklist de fases al inicio de `docs/08-roadmap-fases.md`.
