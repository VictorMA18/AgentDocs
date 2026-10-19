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

### ADR-009 · PyTorch solo CPU
- **Contexto:** `sentence-transformers` depende de PyTorch, que en Linux se instala por defecto con CUDA (~4-5 GB). El modelo MiniLM multilingüe es pequeño y la indexación de documentación son pocos fragmentos.
- **Decisión:** instalar `torch` desde el índice CPU de PyTorch (`--index-url https://download.pytorch.org/whl/cpu`) antes del resto de dependencias.
- **Consecuencias:** entorno de ~1,4 GB y reproducible en máquinas sin GPU; indexar un documento corto tarda ~1 s tras cargar el modelo (~10 s la primera vez, con descarga).

### ADR-010 · Resultado de búsqueda en etiquetas `<documento>` con cierre neutralizado
- **Contexto:** los documentos indexados son datos no confiables; un documento podría contener `</documento>` seguido de instrucciones para escapar de la etiqueta. docs/04 describía dos formatos distintos para el resultado.
- **Decisión:** `buscar_documentos` devuelve `<documento fuente="archivo#n" seccion="…" score="0.82">texto</documento>` por fragmento, cambia `</documento` por `<\/documento` dentro del texto y el system prompt (reglas fijas, no modificables por la skill) declara ese contenido como dato. Las herramientas de juguete de la Fase 1 pasan a `tests/fakes.py`.
- **Consecuencias:** la defensa es de mejor esfuerzo (el modelo podría seguir obedeciendo texto malicioso dentro de la etiqueta); se medirá con el caso de documento envenenado de la Fase 7. `MIN_SCORE` sigue en 0,25.

### ADR-011 · Memoria recortada con resumen de los turnos antiguos
- **Contexto:** el CLI no guarda estado, así que cada llamada reenvía todo el historial; con búsquedas, cada pregunta añade miles de tokens y la conversación se encarece y se alarga sin límite.
- **Decisión:** al superar un umbral estimado (`MEMORY_MAX_TOKENS`, caracteres/4) se resumen los turnos antiguos con el propio LLM y se conservan los últimos `MEMORY_KEEP_TURNS`; el resumen va en el system prompt y se prohíbe que contenga datos técnicos (deben volver a buscarse en el RAG). Adelanta un punto de la Fase 8.
- **Consecuencias:** una llamada extra al LLM (~4 s) cada vez que se compacta; el resumen puede perder matices (se mitiga porque lo técnico se busca de nuevo); la estimación de tokens es aproximada; un fallo del resumidor no rompe el turno.

### ADR-012 · Herramientas de salida que validan y devuelven feedback (validación heurística v1)
- **Contexto:** el agente debe producir diagramas Mermaid y documentos de requisitos fiables, sin que nuestro código genere contenido con IA ni acepte rutas del modelo.
- **Decisión:** `generar_diagrama` y `generar_requisitos` validan con reglas propias (cabecera acorde al tipo, corchetes balanceados, ids únicos, prioridad MoSCoW, criterio/métrica presentes), devuelven todos los errores a la vez como `is_error` y solo guardan si todo es válido. Los nombres de archivo son `prefijo-slug-id` generados por el sistema (`outputs/naming.py`, creación exclusiva) y al modelo solo se le devuelve el nombre.
- **Consecuencias:** el modelo se autocorrige sin intervención humana (cubierto con cliente falso y confirmado en real al forzarlo con un Mermaid roto; no apareció de forma natural en las pruebas de aceptación); la validación no garantiza que Mermaid renderice (v2 con `mermaid-cli` en la Fase 8); los avisos (requisito sin fuente) no bloquean.

*(Añade aquí: ADR-013…)*

## Tabla de experimentos (rellenar en Fases 4 y 7)

| Fecha | Cambio | Métrica afectada | Antes | Después | Conclusión |
|---|---|---|---|---|---|
| 2026-10-16 | Línea base de recuperación (Fase 2, MiniLM multilingüe, chunk 700/100) | Score del mejor fragmento | — | "reintentos": 0,243 · "¿cuántos reintentos hace una tarea por defecto?": 0,591 · "concurrencia por defecto del worker": 0,739 · fuera de tema ("receta de pizza"): 0,209 | Las consultas de una palabra puntúan bajo y quedan por debajo de `MIN_SCORE=0,25`; revisar el umbral en la Fase 3 con el dataset de evaluación |
| 2026-10-17 | Aceptación de la Fase 3 (Haiku 5.5 + MiniLM, `MIN_SCORE=0,25`) | Comportamiento del agente | — | "hola": 0 búsquedas · concurrencia del worker: 1 búsqueda, respuesta "4" con cita [taskflow.md#4] · Kubernetes+Helm: 2 búsquedas, dice que la documentación no lo cubre y marca lo general como tal · pregunta compuesta: 2 búsquedas · regla extra en una copia de `SKILL.md`: respuesta cambia de formato sin tocar código | Cumple los 5 criterios; el umbral 0,25 se mantiene hasta tener dataset (Fase 7) |
| 2026-10-17 | Memoria recortada (`MEMORY_MAX_TOKENS=1500`, `KEEP_TURNS=2`, 5 preguntas) | Tokens de entrada por pregunta | 10.097 → 12.807 → 15.923 (crece sin recorte) | 16.845 → 17.278 con compactación (2 compactaciones, ~4 s cada una) | El crecimiento se frena; el resumen no contiene valores técnicos y la pregunta repetida volvió a usar `buscar_documentos` |
| 2026-10-17 | Aceptación de la Fase 3b (Haiku 5.5) | Comportamiento del agente | — | Secuencia "encolar y procesar": 2 búsquedas + `generar_diagrama` (ok a la primera) · estados: 1 búsqueda + diagrama · requisitos de reintentos: 1 búsqueda + 5 RF con fuente y criterio, sin avisos · en los 3 casos citas y supuestos marcados | Cumple; la autocorrección no apareció de forma natural (ver fila siguiente) |
| 2026-10-18 | Autocorrección forzada y diagrama "tal cual" (Haiku 5.5) | Comportamiento ante Mermaid inválido | — | Mermaid roto: la herramienta lo rechazó con la lista de errores y el modelo lo corrigió y guardó en la siguiente llamada · código del usuario "tal cual": el modelo lo corregía en silencio; con la excepción añadida a la skill muestra los errores, propone la versión corregida y pregunta | La autocorrección funciona en real; el caso "tal cual" se arregló en la skill (ver tabla de fallos) |

## Fallos encontrados y cómo se arreglaron (rellenar durante el desarrollo)

| Fallo observado | Causa | Corrección | Caso añadido al dataset |
|---|---|---|---|
| Con solape, un fragmento de párrafo largo superaba `chunk_size` | Cada trozo ocupaba todo el presupuesto y luego se le añadía la cola de solape | Partir el párrafo en trozos de `presupuesto − solape` (`tests/rag/test_chunking.py::test_long_paragraph_is_split_with_overlap`) | — (test unitario) |
| `.gitignore` con `outputs/` ignoraba también `src/techdoc_agent/outputs/` y `tests/outputs/` (el código nuevo no aparecía en `git status`) | La regla sin `/` inicial coincide con cualquier carpeta de ese nombre | Cambiar a `/outputs/` (solo la carpeta raíz de artefactos) | — (config de git) |
| La consulta "cómo integro TaskFlow con Kubernetes" puntúa 0,64 con el fragmento de portada | La búsqueda vectorial se deja llevar por el nombre del producto aunque el tema no esté en la documentación | Mitigado en la skill ("evalúa la evidencia"): en la aceptación de la Fase 3 el agente declaró que la documentación no lo cubre. El retriever sigue devolviendo la portada con 0,64. Una sola ejecución, no una medida | `fuera-alcance-k8s` (ya en `evals/dataset.example.jsonl`); se mide en la Fase 7 y la búsqueda híbrida (Fase 8) solo se justifica si la tasa de acierto es baja |
| El modelo conjeturó que "el índice puede estar incompleto" ante una respuesta sin resultados | Sin regla que lo prohíba, rellena el hueco con una hipótesis sobre el sistema | Regla en `SKILL.md` ("No especular sobre el estado del sistema ni del índice") | — (pendiente de dataset, Fase 7) |
| Con un diagrama Mermaid roto que el usuario pidió guardar "tal cual", el modelo lo corrigió en silencio | La skill pedía corregir los errores de la herramienta sin distinguir el código aportado por el usuario | Excepción en `SKILL.md` (diagramas, paso 4): mostrar errores, proponer la versión corregida y preguntar | — (pendiente de dataset, Fase 7) |

## Glosario

- **Agente:** sistema donde el LLM decide, en un bucle, qué herramientas usar y cuándo terminar.
- **Workflow:** flujo de pasos predefinido por código que usa LLMs en algunos pasos.
- **Tool use / function calling:** capacidad del modelo de pedir la ejecución de una función con argumentos estructurados.
- **`tool_use` / `tool_result`:** bloques de mensaje de la API nativa: el modelo pide una herramienta; tu código responde con el resultado. Aquí no se usan (ADR-008): el equivalente es el protocolo JSON `accion: herramientas|responder` y los mensajes `<resultado_herramienta>`.
- **`stop_reason`:** en la API nativa, por qué el modelo dejó de generar (`tool_use`, `end_turn`, `max_tokens`…). Aquí el bucle decide por el campo `accion` de la respuesta.
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
- **Compactación de memoria:** sustituir los turnos antiguos del historial por un resumen para limitar el contexto enviado al modelo.
- **Mermaid:** lenguaje de texto para describir diagramas.
- **MoSCoW:** priorización Must/Should/Could/Won't.
- **Groundedness:** grado en que una respuesta está respaldada por las fuentes.
- **Hit@k:** proporción de casos donde la fuente correcta aparece entre los k primeros resultados.
