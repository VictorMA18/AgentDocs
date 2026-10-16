# 09 · Decisiones (ADR) y glosario

## Registro de decisiones

Formato: contexto → decisión → consecuencias. Añade una entrada cada vez que cambies algo importante.

### ADR-001 · Sin frameworks de agentes
- **Contexto:** El objetivo es aprender y demostrar cómo funciona un agente.
- **Decisión:** bucle escrito a mano sobre un cliente LLM propio (SDK de Anthropic en el diseño original; sustituido por el CLI de Claude Code en ADR-008).
- **Consecuencias:** más código inicial, pero control total y comprensión; migrar a un framework después es fácil.

### ADR-002 · RAG como herramienta, no como pipeline
- **Contexto:** Un pipeline siempre busca antes de responder; no puede reformular ni omitir la búsqueda.
- **Decisión:** `buscar_documentos` es una herramienta que el LLM invoca cuando lo estima necesario.
- **Consecuencias:** el comportamiento depende de la descripción de la herramienta y de la skill; requiere evaluaciones para verificarlo. Mayor costo en tokens por turno que un pipeline de una sola llamada.

### ADR-003 · JSON + numpy primero, ChromaDB después
- **Contexto:** Se quiere entender qué hace una base vectorial.
- **Decisión:** implementar `VectorStore` con JSON+numpy y luego con Chroma, misma interfaz.
- **Consecuencias:** doble implementación, pero tests compartidos y una comparación documentable.

### ADR-004 · Núcleo + adaptadores (web y MCP)
- **Decisión:** `core/` y `rag/` no dependen de `api/` ni de `mcp_server`.
- **Consecuencias:** se puede añadir otro adaptador (CLI, Slack…) sin tocar el núcleo.

### ADR-005 · Embeddings locales multilingües
- **Contexto:** Anthropic no ofrece modelo de embeddings propio; la documentación suele estar en español; el modelo por defecto de Chroma es solo inglés.
- **Decisión:** `sentence-transformers` con modelo multilingüe, detrás de la interfaz `Embedder`.
- **Consecuencias:** sin segunda API key ni costo por consulta; descarga de modelo en la primera ejecución; calidad inferior a servicios especializados (se puede cambiar por la interfaz).

### ADR-006 · Herramientas que validan en vez de generar
- **Decisión:** el LLM escribe Mermaid/requisitos; la herramienta valida y devuelve errores.
- **Consecuencias:** el agente se autocorrige con feedback concreto; la validación v1 es heurística y puede dejar pasar errores sutiles.

### ADR-007 · Dependencias instaladas por fase
- **Contexto:** `requirements.txt` incluye dependencias de todas las fases; `sentence-transformers` (PyTorch) y `chromadb` pesan varios GB.
- **Decisión:** en cada fase se instalan solo las dependencias que esa fase necesita. `pyproject.toml` no declara `dependencies`; `requirements.txt` sigue siendo la fuente única.
- **Consecuencias:** entorno ligero al principio; al empezar las Fases 2, 4, 5 y 6 hay que instalar sus dependencias. `pip install -r requirements.txt` sigue funcionando para instalar todo.

### ADR-008 · LLM mediante el CLI de Claude Code (sin API key)
- **Contexto:** no se puede obtener una API key de Anthropic; sí hay acceso al CLI `claude` con sesión iniciada. Reemplaza al SDK de Anthropic de ADR-001.
- **Decisión:** el LLM se invoca con `claude -p --model claude-haiku-5-5 --tools "" --no-session-persistence --output-format json`, detrás de una interfaz `LLMClient`. El bucle sigue siendo propio; las herramientas se piden con un protocolo JSON definido por nosotros (`--json-schema`) en vez de `tool_use` nativo.
- **Consecuencias:** sin API key ni costo por token adicional (consume el uso de Claude Code); mayor latencia por proceso lanzado en cada llamada; sin control de `max_tokens` (se limita con `LLM_TIMEOUT_S`); el formato de herramientas depende de que el modelo respete el schema, por lo que hay que validarlo y tratar los fallos como errores recuperables; cambiar a la API o a otro modelo es implementar otro `LLMClient`. Se retiran `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `MAX_TOKENS` y la dependencia `anthropic`.

*(Añade aquí: ADR-009…)*

## Tabla de experimentos (rellenar en Fases 4 y 7)

| Fecha | Cambio | Métrica afectada | Antes | Después | Conclusión |
|---|---|---|---|---|---|
| | | | | | |

## Fallos encontrados y cómo se arreglaron (rellenar durante el desarrollo)

| Fallo observado | Causa | Corrección | Caso añadido al dataset |
|---|---|---|---|
| | | | |

## Glosario

- **Agente:** sistema donde el LLM decide, en un bucle, qué herramientas usar y cuándo terminar.
- **Workflow:** flujo de pasos predefinido por código que usa LLMs en algunos pasos.
- **Tool use / function calling:** capacidad del modelo de pedir la ejecución de una función con argumentos estructurados.
- **`tool_use` / `tool_result`:** bloques de mensaje: el modelo pide una herramienta; tu código responde con el resultado.
- **`stop_reason`:** por qué el modelo dejó de generar (`tool_use`, `end_turn`, `max_tokens`…).
- **RAG:** generación aumentada por recuperación; el modelo responde apoyándose en fragmentos recuperados.
- **Embedding:** representación vectorial del significado de un texto.
- **Similitud coseno:** medida de cercanía entre vectores.
- **Chunk / fragmento:** porción de un documento que se indexa como unidad.
- **Solape (overlap):** texto repetido entre fragmentos contiguos para no cortar ideas.
- **Top-k:** los k resultados más similares.
- **Alucinación:** afirmación sin respaldo en las fuentes.
- **Inyección de prompt indirecta:** instrucciones maliciosas ocultas en datos (documentos) que el modelo podría obedecer.
- **System prompt:** instrucciones de alto nivel que definen rol y reglas del modelo.
- **Skill:** carpeta con instrucciones (`SKILL.md`) sobre cómo realizar un tipo de tarea.
- **MCP (Model Context Protocol):** estándar para exponer herramientas/recursos a clientes de IA.
- **stdio:** transporte MCP donde el cliente lanza el servidor como subproceso y habla por entrada/salida estándar.
- **SSE (Server-Sent Events):** flujo unidireccional servidor→navegador, útil para streaming de tokens.
- **Mermaid:** lenguaje de texto para describir diagramas.
- **MoSCoW:** priorización Must/Should/Could/Won't.
- **Groundedness:** grado en que una respuesta está respaldada por las fuentes.
- **Hit@k:** proporción de casos donde la fuente correcta aparece entre los k primeros resultados.
