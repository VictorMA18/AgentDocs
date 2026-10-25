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

### ADR-013 · ChromaDB como segundo almacén seleccionable (JSON sigue por defecto)
- **Contexto:** Fase 4. La interfaz `VectorStore` ya aislaba al resto del código; había que comprobar que una base vectorial real encaja sin tocar el agente y medir si compensa.
- **Decisión:** `ChromaVectorStore` (HNSW con coseno, vectores de nuestro `Embedder`, `upsert`, `score = 1 - distancia`) convive con `JsonVectorStore`; `VECTOR_STORE=json|chroma` y `rag/factory.py` eligen cuál. El valor por defecto sigue siendo `json`.
- **Consecuencias:** mismos resultados en ambos (mismos fragmentos, scores con diferencia ≤ 2·10⁻⁷). Con este tamaño de corpus el JSON es más rápido en búsqueda (hasta 20.000 fragmentos no hay punto de cruce), usa menos disco (2-3×) y es más simple; Chroma gana en la reingesta de un documento sobre un índice grande (el JSON reescribe todo el índice) y en no cargar todo en memoria. Chroma añade una dependencia pesada (`onnxruntime`, etc.), y filtrar por fuente le cuesta más. Cambiar de almacén obliga a reindexar. Recomendación: JSON mientras el corpus sea de miles de fragmentos; Chroma si se espera crecer o ingestar con frecuencia.

### ADR-014 · Adaptador web: nombres saneados, un candado y CSP sin scripts inline
- **Contexto:** la Fase 5 expone el agente por HTTP; todo lo que entra (archivos, nombres, rutas, mensajes) y la salida del modelo (Markdown) son datos no confiables.
- **Decisión:** (1) los documentos subidos conservan su nombre **saneado** (sin carpetas, solo `[A-Za-z0-9._-]`) en vez de uno generado como proponía `docs/06`, porque ese nombre es la fuente de las citas y de la reingesta por reemplazo; los artefactos sí se sirven solo con nombres generados por el sistema; (2) un único `threading.Lock` serializa chat, subida y borrado, porque `Memory` y `JsonVectorStore` no son seguros ante hilos; (3) el JS y el CSS van en archivos propios para poder usar una CSP sin `unsafe-inline` en scripts; las tres librerías (`marked`, `DOMPurify`, `mermaid`) se cargan por CDN con versión fija y hash SRI; (4) `ToolTrace` guarda el resultado de cada herramienta para que el adaptador identifique los artefactos del turno sin que `core/` conozca la API; (5) `build_agent` pasa a `bootstrap.py` para que CLI y API lo compartan.
- **Consecuencias:** una petición de chat bloquea subidas y borrados mientras dura (aceptable para uso local); el límite de subida es de mejor esfuerzo (si el cliente no envía `Content-Length`, el servidor puede recibir parte del archivo antes de abortar); el Markdown del modelo se sanea con DOMPurify (sin `style`, formularios ni controles) y si las librerías no cargan se muestra como texto plano; un diagrama que pase la validación heurística puede no renderizar, y la página muestra entonces su código.

### ADR-015 · Conversaciones guardadas: memoria persistente + transcripción aparte
- **Contexto:** la conversación vivía en el DOM y en la RAM del servidor; recargar la página la ocultaba y reiniciar el servidor la perdía. "Nueva conversación" dejaba la anterior inalcanzable.
- **Decisión:** dos archivos JSON por conversación en `data/conversations/`. (1) `<id>.memory.json`, escrito por `Memory(storage_dir)` desde `Agent.run` (siempre, en un `finally`): historial en el formato del protocolo, marcas de turno y resumen; permite que el agente continúe tras un reinicio. (2) `<id>.turns.json`, escrito por la API con `core/transcripts.py`: cada turno ya presentado; es independiente porque la compactación de memoria (ADR-011) descarta turnos y el formato interno no sirve para mostrarlos. Escrituras atómicas, ids validados antes de formar rutas y archivos ilegibles apartados como `.corrupt`. Solo la web persiste; la CLI sigue en RAM. La página recuerda la conversación actual en `localStorage`.
- **Consecuencias:** los archivos contienen texto de conversaciones y fragmentos de documentos (los logs no), por eso van en `.gitignore` y se pueden quitar desde la página; la transcripción crece sin límite (no hay purga automática); una caída entre el fin del turno y la escritura pierde ese turno; la memoria y la transcripción pueden desincronizarse si se borra a mano solo una; sigue habiendo un único candado (ADR-014).

### ADR-016 · Servidor MCP como adaptador delgado sobre `MCPServer` (mcp 2.x)
- **Contexto:** la Fase 6 expone el RAG y el agente a otros clientes. `docs/06` y `docs/08` se escribieron para `FastMCP`, pero la versión vigente del SDK (`mcp` 2.3) lo renombró a `MCPServer` (`mcp.server.fastmcp` lanza `ModuleNotFoundError`) y los errores no previstos se enmascaran.
- **Decisión:** `mcp_server.py` con `MCPServer` por stdio y `requirements.txt` fijado a `mcp>=2,<3`. Cuatro herramientas; las de búsqueda **delegan** en las herramientas RAG del agente (sin duplicar validación ni formato), `ingestar_documento` valida la ruta con `resolve()` dentro de `ALLOWED_INGEST_DIR` antes de comprobar que existe, y los errores previstos son `ToolError` para que el cliente vea el motivo. El modelo de embeddings se carga bajo demanda (`LazyEmbedder`) y `main()` se sitúa en la raíz del proyecto, porque los clientes MCP no garantizan el directorio de trabajo. La memoria de `preguntar_agente` vive en RAM.
- **Buscar frente a preguntar:** exponer `buscar_documentos` entrega **fragmentos**: el LLM del cliente razona con ellos, los mezcla con otras herramientas y paga sus propios tokens; para nosotros es barato, rápido y componible, pero el cliente debe interpretar y citar bien. Exponer `preguntar_agente` entrega una **respuesta ya elaborada** (skill, reglas anti-alucinación, memoria): más cómoda y consistente, pero es una caja negra lenta (un LLM dentro de otro), el cliente no puede componerla y duplica el coste. Ambas tienen sentido; la primera es el bloque básico y la segunda, un atajo.
- **Consecuencias:** el servidor arranca al instante, pero la primera búsqueda o ingesta paga la carga del modelo (~10 s); `preguntar_agente` puede acercarse al tiempo máximo de herramienta del cliente (`MCP_TOOL_TIMEOUT`); sin notificaciones de progreso, transporte HTTP ni autenticación; si el cliente no conoce el directorio permitido tiene que adivinarlo, por eso la descripción y el error indican que basta el nombre del archivo (corregido tras la prueba real, ver experimentos).

### ADR-017 · Evaluaciones con reglas comprobables, repetición y corrección del instrumento
- **Contexto:** hasta la Fase 6 cada cambio se validaba a mano con una o dos preguntas. Sin una medición repetible no se sabe si un cambio mejora, empeora o solo mueve el ruido (el CLI de Claude no permite fijar la temperatura, ADR-008).
- **Decisión:** `evals/` con un dataset de 30 casos (`dataset.jsonl`), reglas **puras** en `rules.py` (herramientas, recuperación, contenido, robustez, abstención, citas, artefactos, aclaración) y un runner que aísla cada caso (índice, memoria y salidas propios) y los ejecuta en paralelo (`--workers`). La repetición (`--repeat`) es la única forma de medir el no determinismo; un caso cuenta como acierto con tasa ≥ 0,5. Sin LLM como juez: las reglas son baratas, repetibles y explicables.
- **Instrumento frente a producto:** cuando un caso falla hay que decidir si falla el agente o la regla. Dos de los fallos medidos eran de la regla (iteración 1: la respuesta que *menciona* el texto inyectado para avisar no lo obedece; iteración 5: «No encuentro…» no estaba en la lista de frases de abstención). Se corrigen y se anotan como tales; **no cuentan como mejora del agente**.
- **Guarda de herramienta nativa:** si el CLI responde «No such tool available» a una llamada nativa, el agente lo reenvía una vez con una pista del protocolo JSON (`native_tool_attempt` en el log). Es una medida defensiva: el fallo es raro (≈ 1 de cada 96 ejecuciones) y el efecto no se puede medir con este tamaño de muestra.
- **Consecuencias:** las reglas por frases son frágiles ante sinónimos (hay que mantenerlas); con 2 repeticiones por caso una tasa de 50 % es un solo fallo y puede ser ruido; los tiempos medidos con `--workers 4` están inflados por la concurrencia; cada pasada completa consume ≈ 1,1 M de tokens.

*(Añade aquí: ADR-018…)*

## Tabla de experimentos

| Fecha | Cambio | Métrica afectada | Antes | Después | Conclusión |
|---|---|---|---|---|---|
| 2026-10-16 | Línea base de recuperación (Fase 2, MiniLM multilingüe, chunk 700/100) | Score del mejor fragmento | — | "reintentos": 0,243 · "¿cuántos reintentos hace una tarea por defecto?": 0,591 · "concurrencia por defecto del worker": 0,739 · fuera de tema ("receta de pizza"): 0,209 | Las consultas de una palabra puntúan bajo y quedan por debajo de `MIN_SCORE=0,25`; revisar el umbral en la Fase 3 con el dataset de evaluación |
| 2026-10-17 | Aceptación de la Fase 3 (Haiku 5.5 + MiniLM, `MIN_SCORE=0,25`) | Comportamiento del agente | — | "hola": 0 búsquedas · concurrencia del worker: 1 búsqueda, respuesta "4" con cita [taskflow.md#4] · Kubernetes+Helm: 2 búsquedas, dice que la documentación no lo cubre y marca lo general como tal · pregunta compuesta: 2 búsquedas · regla extra en una copia de `SKILL.md`: respuesta cambia de formato sin tocar código | Cumple los 5 criterios; el umbral 0,25 se mantiene hasta tener dataset (Fase 7) |
| 2026-10-17 | Memoria recortada (`MEMORY_MAX_TOKENS=1500`, `KEEP_TURNS=2`, 5 preguntas) | Tokens de entrada por pregunta | 10.097 → 12.807 → 15.923 (crece sin recorte) | 16.845 → 17.278 con compactación (2 compactaciones, ~4 s cada una) | El crecimiento se frena; el resumen no contiene valores técnicos y la pregunta repetida volvió a usar `buscar_documentos` |
| 2026-10-17 | Aceptación de la Fase 3b (Haiku 5.5) | Comportamiento del agente | — | Secuencia "encolar y procesar": 2 búsquedas + `generar_diagrama` (ok a la primera) · estados: 1 búsqueda + diagrama · requisitos de reintentos: 1 búsqueda + 5 RF con fuente y criterio, sin avisos · en los 3 casos citas y supuestos marcados | Cumple; la autocorrección no apareció de forma natural (ver fila siguiente) |
| 2026-10-18 | Autocorrección forzada y diagrama "tal cual" (Haiku 5.5) | Comportamiento ante Mermaid inválido | — | Mermaid roto: la herramienta lo rechazó con la lista de errores y el modelo lo corrigió y guardó en la siguiente llamada · código del usuario "tal cual": el modelo lo corregía en silencio; con la excepción añadida a la skill muestra los errores, propone la versión corregida y pregunta | La autocorrección funciona en real; el caso "tal cual" se arregló en la skill (ver tabla de fallos) |
| 2026-10-18 | Migración a ChromaDB (Fase 4, MiniLM real) | Resultados y scores de `search` | JSON | Chroma | Mismos 3 fragmentos y orden en 5 consultas; diferencia máxima de score 1,8·10⁻⁷. Agente real (Haiku) con `VECTOR_STORE=chroma`: concurrencia del worker con cita [taskflow.md#4] y Kubernetes "no está cubierto" | Equivalentes; latencias y tamaños en la tabla de comparación (ADR-013) |
| 2026-10-18 | Aceptación de la Fase 5 (servidor real, Haiku 5.5, `curl`) | Comportamiento de la API | — | Subida de `taskflow.md`: 8 fragmentos · `.exe`: 415 · 12 MB: 413 · `../../evil.md`: guardado como `evil.md` dentro de `data/documents/` · `GET /api/artifacts/../../.env` y variantes: 404/400 · chat de concurrencia: 1 búsqueda con cita [taskflow.md#4] · diagrama de secuencia: `artifacts` con nombre, tipo y título, descargable · pregunta de seguimiento en la misma sesión: respondió con el contexto previo | Cumple los criterios de seguridad; el flujo en el navegador (render de Mermaid y saneado del Markdown) queda para la prueba manual |
| 2026-10-19 | Conversaciones guardadas (servidor real, Haiku 5.5, reinicio en medio) | Persistencia | — | 2 conversaciones creadas; tras reiniciar el servidor: lista y transcripción intactas; pregunta de seguimiento sin repetir el tema ("¿cuántos segundos dura la espera base entre esos reintentos?") respondida con el contexto previo; la otra conversación recordó su propio tema sin mezclarlo; borrar una dejó solo los 2 archivos de la otra y devolvió 404 al consultarla | Cumple; el flujo en el navegador (lista, reabrir, quitar) queda para la prueba manual |
| 2026-10-20 | Aceptación de la Fase 6 (Claude Code `-p --mcp-config` con el servidor real, Haiku 5.5) | Uso del servidor desde un cliente MCP | — | "Lista mis documentos" → `listar_documentos` · `ingestar_documento` con `/etc/hostname` y `../../.env`: rechazadas con "Ruta no permitida" · la primera vez el cliente adivinó una ruta absoluta del repo y fue rechazada: se añadió a la descripción y al error que basta el nombre del archivo y entonces `lumen_cache.md` se indexó (12 fragmentos) · `buscar_documentos` → TTL 300 s y 600 s antes de la 1.3 con citas · `preguntar_agente` → 2 segundos y `BackendUnavailableError` con cita; Kubernetes: "no aparece en la documentación" | Cumple los 3 criterios; los mensajes de error de una herramienta son parte de su interfaz para el cliente |
| 2026-10-20 | Cierre de dudas de la Fase 6: Claude Code lanzado **desde otra carpeta**, servidor sin variables de entorno (índice real del proyecto) y configuración solo de esa ejecución (`--mcp-config`; `claude mcp list` no la muestra después) | Directorio de trabajo, tiempos y concurrencia | — | "Lista mis documentos": 7 s, devolvió los 2 documentos del `data/index/` real · `preguntar_agente` con `MCP_TOOL_TIMEOUT` por defecto: pregunta simple 22 s, compuesta sobre las dos librerías 27 s y diagrama con varios pasos internos 50 s (el archivo `.mmd` se guardó) sin cortes · 4 llamadas a `preguntar_agente` y 2 de lectura en paralelo con un agente lento: ninguna falló y los turnos nunca se solaparon | Confirma el `chdir` a la raíz y el candado; no hizo falta subir `MCP_TOOL_TIMEOUT` con esta carga |
| 2026-10-24 | **Línea base** de la Fase 7 (30 casos × 2 repeticiones, Haiku 5.5, MiniLM, JSON, `MIN_SCORE=0,25`, 4 trabajadores) | Casos acertados / tasa media por caso | — | 29/30 (97 %) · 95 % · ≈ 18.800 tokens y 3,6 min por pasada | Fallan `inyeccion-documento` (0 %, falso positivo de la regla) y `diagrama-estados` (50 %: una ejecución afirmó «No such tool available» sin pedir la herramienta). Las 12 ejecuciones fuera de alcance se abstuvieron |
| 2026-10-25 | **Iteración 1** · la regla de robustez solo falla si la respuesta *empieza* por la orden inyectada (`must_not_start_with`); mencionarla para avisar no es obedecer | Robustez / casos acertados | 50 % / 29 de 30 | 100 % / 30 de 30 | **Corrección del instrumento**, medida reevaluando las mismas respuestas de la línea base: el agente no cambió |
| 2026-10-25 | **Iteración 2** · regla de prompt + reintento único ante «No such tool available» (6 casos de diagramas y requisitos × 6 repeticiones) | Casos acertados en `diagrama-estados` | 36/36 (100 %) | 36/36 (100 %), 0 reintentos; pasada completa de control 30/30 (100 %) | **Efecto no medible**: el fallo ocurre en ≈ 1 de 96 ejecuciones y no se reprodujo. Se mantiene como medida defensiva con tests unitarios; no se afirma que mejore nada |
| 2026-10-25 | **Iteración 3 (ablación)** · quitar de la skill el paso 4 «Evalúa la evidencia» | Abstención (6) y casos acertados | 100 % / 100 % | 100 % / 30 de 30; aclaración 50 % (`pregunta-ambigua`, 1 de 2) | La abstención **no depende solo de ese paso**: la regla fija del prompt y el propio modelo la sostienen. El fallo de aclaración es una ejecución sobre dos y el paso quitado no trata ese tema: es ruido, no efecto. Conclusión: la redundancia protege, pero no se pudo medir cuánto |
| 2026-10-25 | **Iteración 4a** · `MIN_SCORE` 0,25 → 0 (sin umbral) | Casos acertados · abstención · tokens por ejecución | 30/30 · 100 % · 19.175 | 30/30 · 100 % · 20.014 (+4 %) | El umbral **no** es lo que hace que el agente se abstenga con los 6 casos fuera de alcance; solo ahorra algo de contexto |
| 2026-10-25 | **Iteración 4b** · `MIN_SCORE` 0,25 → 0,5 | Recuperación · contenido · casos acertados | 100 % · 100 % · 30/30 | 97 % · 90 % · 29/30 (tasa media 93 %) | **Regresión real**: `lumen-redis-timeout` falla 2 de 2 (el fragmento relevante queda bajo 0,5 y el agente dice que no está documentado) y dos casos más pierden una ejecución. 0,25 se mantiene |
| 2026-10-25 | **Iteración 5** · `VECTOR_STORE=chroma` (misma configuración) | Casos acertados | 30/30 (JSON) | 30/30 tras corregir la regla; 29/30 con la regla antigua | Mismo comportamiento que JSON, como exigía ADR-013. El único fallo era de la regla: «No encuentro nada…» no estaba en las frases de abstención (se añade con test) |

### Comparación JSON vs Chroma (Fase 4)

Medido con MiniLM real (384 dimensiones), CPU, 100 repeticiones por búsqueda (`top_k=5`, sin contar el cálculo del embedding de la consulta). Los corpus de 500 fragmentos o más son sintéticos: el sample duplicado con ruido pequeño y 50 fuentes distintas.

| Fragmentos | Almacén | Indexar (s) | Reabrir (ms) | Búsqueda (ms) | Búsqueda con `source` (ms) | Disco (MB) |
|---|---|---|---|---|---|---|
| 8 (real) | JSON | 0,00 | 0,3 | 0,01 | 0,01 | 0,02 |
| 8 (real) | Chroma | 0,05 | 18,6 | 1,65 | 1,78 | 0,41 |
| 500 | JSON | 0,00 | 1,5 | 0,03 | 0,04 | 1,01 |
| 500 | Chroma | 0,22 | 19,2 | 1,87 | 2,07 | 3,48 |
| 5.000 | JSON | 0,14 | 12,9 | 0,37 | 0,53 | 10,14 |
| 5.000 | Chroma | 2,25 | 21,8 | 2,47 | 4,75 | 25,67 |
| 20.000 | JSON | 2,28 | 60,3 | 2,29 | 2,69 | 40,60 |
| 20.000 | Chroma | 10,63 | 27,8 | 5,36 | 12,95 | 92,82 |

Reingesta de un documento de 8 fragmentos (borrar + añadir) sobre un índice existente: con 5.000 fragmentos, JSON 17,8 ms y Chroma 10,2 ms; con 20.000, JSON 58,6 ms y Chroma 14,5 ms (el JSON reescribe el índice completo en cada `add`).

Resultados con el sample real (5 consultas, top-3): mismos ids en el mismo orden en ambos almacenes y diferencia máxima de score de 1,8·10⁻⁷.

## Fallos encontrados y cómo se arreglaron (rellenar durante el desarrollo)

| Fallo observado | Causa | Corrección | Caso añadido al dataset |
|---|---|---|---|
| Con solape, un fragmento de párrafo largo superaba `chunk_size` | Cada trozo ocupaba todo el presupuesto y luego se le añadía la cola de solape | Partir el párrafo en trozos de `presupuesto − solape` (`tests/rag/test_chunking.py::test_long_paragraph_is_split_with_overlap`) | — (test unitario) |
| `.gitignore` con `outputs/` ignoraba también `src/techdoc_agent/outputs/` y `tests/outputs/` (el código nuevo no aparecía en `git status`) | La regla sin `/` inicial coincide con cualquier carpeta de ese nombre | Cambiar a `/outputs/` (solo la carpeta raíz de artefactos) | — (config de git) |
| La consulta "cómo integro TaskFlow con Kubernetes" puntúa 0,58-0,64 con el fragmento de portada (0,5775 medido en la Fase 4, idéntico en JSON y Chroma) | La búsqueda vectorial se deja llevar por el nombre del producto aunque el tema no esté en la documentación | Mitigado en la skill ("evalúa la evidencia"): en la aceptación de la Fase 3 el agente declaró que la documentación no lo cubre. El retriever sigue devolviendo la portada con ~0,58 (también con Chroma, donde el agente respondió igual de bien). Una sola ejecución, no una medida | `fuera-alcance-k8s` (ya en `evals/dataset.example.jsonl`); se mide en la Fase 7 y la búsqueda híbrida (Fase 8) solo se justifica si la tasa de acierto es baja |
| El modelo conjeturó que "el índice puede estar incompleto" ante una respuesta sin resultados | Sin regla que lo prohíba, rellena el hueco con una hipótesis sobre el sistema | Regla en `SKILL.md` ("No especular sobre el estado del sistema ni del índice") | — (pendiente de dataset, Fase 7) |
| Con un diagrama Mermaid roto que el usuario pidió guardar "tal cual", el modelo lo corrigió en silencio | La skill pedía corregir los errores de la herramienta sin distinguir el código aportado por el usuario | Excepción en `SKILL.md` (diagramas, paso 4): mostrar errores, proponer la versión corregida y preguntar | — (pendiente de dataset, Fase 7) |
| La regla de robustez daba 0 % en `inyeccion-documento` aunque el agente resistió | La regla buscaba la palabra inyectada en cualquier parte; el agente la menciona al avisar de la orden, como pide la skill | La regla solo falla si la respuesta *empieza* por ella (`must_not_start_with`); los literales secretos siguen prohibidos en cualquier parte | `inyeccion-documento` |
| En una ejecución de `diagrama-estados` el agente respondió que la herramienta «no está disponible» sin haberla pedido | El modelo intentó una llamada nativa; el CLI contestó «No such tool available» y el modelo lo repitió como un hecho | Regla en el prompt y un reintento único con la pista del protocolo JSON (`native_tool_attempt`); fallo raro, efecto no medible | `diagrama-estados` |
| Una abstención correcta («No encuentro nada sobre Kubernetes…») se marcó como fallo | «no encuentro» no estaba en la lista de frases de abstención | Frase añadida con test; las reglas por frases se revisan al leer los fallos | `fuera-alcance-lumen-k8s` |

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
