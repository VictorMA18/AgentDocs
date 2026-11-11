# 08 · Roadmap por fases

Estado (marca al terminar cada una):

- [x] Fase 0 · Preparación
- [x] Fase 1 · Bucle del agente con herramienta falsa
- [x] Fase 2 · Ingesta + almacén JSON (sin agente)
- [x] Fase 3 · RAG como herramienta + skill
- [x] Fase 3b · Herramientas de diagramas y requisitos
- [x] Fase 4 · Migración a ChromaDB
- [x] Fase 5 · FastAPI + HTML
- [x] Fase 6 · Servidor MCP
- [x] Fase 7 · Evaluaciones, logs y README final
- [x] Fase 7.B · Búsqueda híbrida (BM25 + vectorial), decidida con evaluaciones
- [x] Fase 8 · Progreso en vivo (SSE), skill con divulgación progresiva, validación real de Mermaid y cierre de observaciones

**Cómo usar los prompts:** abre Claude Code en la raíz del proyecto y pega el prompt de la fase. Cuando termine, revisa los criterios de aceptación **tú mismo**, lee el código y pídele que te explique lo que no entiendas antes de pasar a la siguiente.

---

## Fase 0 · Preparación
**Concepto:** estructura, configuración y observabilidad desde el inicio.

**Entregables**
- Entorno virtual, `requirements.txt` instalado, `git init` y primer commit.
- Paquete `src/techdoc_agent/` con `config.py` (lee `.env`) y `logging_setup.py` (JSONL a `logs/`).
- Test que verifica que la configuración carga valores por defecto.

**Aceptación**
- `pytest` pasa.
- `python -c "from techdoc_agent.config import settings; print(settings.model)"` imprime el modelo.
- `.env` no está versionado.

**Prompt para Claude Code**
```
Lee AGENTS.md (incluye el mapa de ubicaciones) y docs/01 a docs/04. Ejecuta la Fase 0 de docs/08-roadmap-fases.md:
crea la estructura de src/techdoc_agent con config.py (variables de .env.example,
usando dataclass y os.environ, sin librerías extra) y logging_setup.py (eventos JSONL
en logs/agent-YYYYMMDD.jsonl, función log_event(**campos)). Añade pyproject.toml mínimo
para instalar el paquete en modo editable y tests básicos. Explícame antes qué vas a
hacer y al final resume los conceptos clave.
```

---

## Fase 1 · Bucle del agente con herramienta falsa
**Concepto:** el ciclo *LLM → tool_use → ejecutar → tool_result → LLM*.

**Entregables**
- `core/tools.py`: registro de herramientas (nombre, descripción, schema, función) y `dispatch()` que captura excepciones y devuelve `(texto, is_error)`.
- `core/llm.py`: interfaz `LLMClient` + `ClaudeCliClient` (llama a `claude -p`, ver `docs/04`) y protocolo JSON de herramientas.
- `core/agent.py`: bucle según `docs/04`, con tope de iteraciones y logging de cada paso.
- `core/memory.py`: historial por `session_id`.
- Dos herramientas de juguete: `obtener_hora` y `sumar(a, b)` (una que falle a propósito con un caso borde).
- `cli.py`: chat por consola.
- Tests con un **cliente LLM falso** (guion de respuestas) que verifican: respuesta directa, una herramienta, dos herramientas en un turno, herramienta que falla, JSON inválido del modelo y tope de iteraciones.

**Aceptación**
- En la consola: "¿qué hora es y cuánto es 17+25?" usa ambas herramientas y responde bien.
- La herramienta que falla no rompe el bucle.
- Se ve en `logs/` cada llamada con duración y tokens.
- Tests pasan sin ejecutar el CLI real.

**Prompt para Claude Code**
```
Ejecuta la Fase 1 de docs/08-roadmap-fases.md siguiendo docs/04-diseno-agente.md.
Escribe el bucle del agente a mano (sin frameworks) usando el CLI de Claude Code como
LLM (ADR-008). Inyecta el cliente LLM como dependencia para poder testear con un cliente
falso. Antes de escribir código, explícame con un diagrama de texto el protocolo JSON de
herramientas y el formato de los mensajes. Comprueba con `claude --help` los flags
exactos. Al final resume qué aprendí.
```

---

## Fase 2 · Ingesta + almacén JSON (sin agente todavía)
**Concepto:** embeddings, chunking y búsqueda por similitud.

**Entregables**
- `rag/loaders.py`, `rag/chunking.py`, `rag/embeddings.py` (interfaz `Embedder` + implementación local multilingüe), `rag/store.py` (interfaz), `rag/store_json.py`, `rag/ingest.py`.
- Script `python -m techdoc_agent.rag.ingest data/sample_docs` y una búsqueda por consola.
- Tests: chunking (tamaños, solape, no partir bloques de código), store (add/search/delete/persistencia), con un `Embedder` falso determinista.

**Aceptación**
- Indexar `data/sample_docs/taskflow.md` y buscar "reintentos" devuelve la sección de reintentos en el top 3.
- Reiniciar el proceso conserva el índice.
- Tests pasan sin descargar modelos (embedder falso).

**Prompt para Claude Code**
```
Ejecuta la Fase 2 de docs/08-roadmap-fases.md siguiendo docs/05-rag.md. Implementa el
almacén JSON + numpy a mano (sin chromadb todavía) detrás de la interfaz VectorStore.
Explícame primero qué es un embedding y por qué se normalizan los vectores, con un
ejemplo numérico pequeño. Quiero un script de consola para ingestar una carpeta y
buscar, y que me muestres los 5 mejores fragmentos con su score para "reintentos".
```

---

## Fase 3 · RAG como herramienta + skill
**Concepto:** el LLM decide cuándo buscar; la skill define el método.

**Entregables**
- Herramientas `buscar_documentos` y `listar_documentos` registradas (docs/04), con resultado formateado en etiquetas `<documento>`.
- `core/skills.py` y `core/prompts.py`: construyen el system prompt con reglas fijas + `SKILL.md`.
- CLI actualizada: comando `/ingestar <ruta>`.
- Quitar las herramientas de juguete (o dejarlas solo en tests).

**Aceptación**
- "hola" → sin herramientas.
- "¿Cuál es la concurrencia por defecto del worker?" → una búsqueda y respuesta correcta con cita.
- Pregunta fuera de la documentación → el agente lo dice y no inventa.
- Pregunta compuesta → dos búsquedas visibles en los logs.
- Cambiar una regla en `SKILL.md` cambia el formato de respuesta sin tocar código.

**Prompt para Claude Code**
```
Ejecuta la Fase 3 de docs/08-roadmap-fases.md. Registra buscar_documentos y
listar_documentos como herramientas del agente usando las descripciones de docs/04.
Construye el system prompt (core/prompts.py) con las reglas fijas y la skill en
skills/documentacion-tecnica/SKILL.md. No hagas ninguna búsqueda fuera del bucle.
Luego prueba los 5 escenarios de aceptación y muéstrame los logs de cada uno.
```

---

## Fase 3b · Herramientas de diagramas y requisitos
**Concepto:** herramientas que **validan** y devuelven errores al modelo para que se autocorrija.

**Entregables**
- `outputs/diagrams.py` (validación heurística v1 + guardado en `outputs/`), herramienta `generar_diagrama`.
- `outputs/requirements_doc.py` (validación + render Markdown), herramienta `generar_requisitos`.
- Nombres de archivo generados por el sistema (slug + id corto), nunca rutas del modelo.
- Tests de validación (casos válidos e inválidos).

**Aceptación**
- "Haz un diagrama de secuencia de encolar y procesar un trabajo" → diagrama guardado, basado en lo recuperado.
- Si el modelo manda Mermaid inválido, la herramienta devuelve errores y el modelo corrige en el siguiente paso (verlo en logs; si no ocurre de forma natural, test con cliente falso).
- "Genera los requisitos de la sección de reintentos" → documento con ids únicos, prioridad y criterios de aceptación.

**Prompt para Claude Code**
```
Ejecuta la Fase 3b de docs/08-roadmap-fases.md con los schemas de docs/04. Las
herramientas generar_diagrama y generar_requisitos no generan contenido con IA: validan
lo que escribe el modelo y devuelven errores claros (is_error) para que se corrija.
Implementa validación heurística de Mermaid (v1). Añade tests con casos inválidos.
Explícame por qué este patrón (validar y devolver feedback) es importante en agentes.
```

---

## Fase 4 · Migración a ChromaDB
**Concepto:** abstracción y comparación de implementaciones.

**Entregables**
- `rag/store_chroma.py` implementando la misma interfaz, usando nuestro `Embedder`.
- `VECTOR_STORE=json|chroma` en configuración.
- Tests parametrizados que corren contra ambos almacenes.
- Comparación antes/después en `docs/09` (resultados, latencia, tamaño).

**Aceptación**
- Mismos tests pasan para ambos almacenes.
- Cambiar la variable de entorno no requiere tocar el agente.
- Los scores de Chroma se convierten a la misma escala que el almacén JSON.

**Prompt para Claude Code**
```
Ejecuta la Fase 4 de docs/08-roadmap-fases.md. Implementa ChromaStore detrás de la
interfaz VectorStore, pasando nuestros embeddings (no uses el embedding por defecto de
Chroma). Verifica la API vigente de chromadb en su documentación. Parametriza los tests
para ambos almacenes. Al final dame una tabla comparativa JSON vs Chroma para añadir a
docs/09-decisiones-y-glosario.md.
```

---

## Fase 5 · FastAPI + HTML
**Concepto:** adaptador de presentación sobre el mismo núcleo.

**Entregables**
- `api/main.py` con los endpoints de `docs/06`; `api/static/index.html` (chat, subida, lista de documentos, panel de herramientas, render de Mermaid).
- Validación de subidas y de nombres de artefactos.
- Tests de la API con `TestClient` (agente simulado).

**Aceptación**
- Flujo completo en el navegador: subir `taskflow.md`, preguntar, ver herramientas usadas, pedir un diagrama y verlo renderizado.
- Subir un `.exe` o un archivo gigante es rechazado con error claro.
- `GET /api/artifacts/../../.env` es rechazado.
- `api/` no contiene lógica de agente ni de RAG.

**Prompt para Claude Code**
```
Ejecuta la Fase 5 de docs/08-roadmap-fases.md siguiendo docs/06-api-y-mcp.md (sección
A). La API y el HTML son un adaptador: solo llaman al núcleo. HTML y JS puro, sin
frameworks. Sanitiza el Markdown renderizado. Añade tests de seguridad para subidas y
descarga de artefactos. Arranca el servidor y dime exactamente qué probar en el navegador.
```

---

## Fase 6 · Servidor MCP
**Concepto:** exponer el agente a otros clientes con un protocolo estándar.

**Entregables**
- `mcp_server.py` con `MCPServer` (en `mcp` 2.x; antes `FastMCP`), herramientas de `docs/06` (sección B), transporte stdio, logs a stderr.
- Documentar en el README cómo conectarlo a Claude Code y a Claude Desktop.
- Test con el cliente MCP del SDK.

**Aceptación**
- `claude mcp add techdoc -- python -m techdoc_agent.mcp_server` y, desde Claude Code, "lista mis documentos" usa tu servidor.
- `ingestar_documento` rechaza rutas fuera de `ALLOWED_INGEST_DIR`.
- `mcp_server.py` no duplica lógica del núcleo.

**Prompt para Claude Code**
```
Ejecuta la Fase 6 de docs/08-roadmap-fases.md siguiendo docs/06-api-y-mcp.md (sección
B). Usa el SDK oficial de Python de MCP (MCPServer; FastMCP en la 1.x) y transporte stdio. Nada de print a
stdout. Verifica la API vigente del SDK en su documentación. Explícame qué diferencia
hay entre exponer buscar_documentos y exponer preguntar_agente, y escribe un test que
llame ambas herramientas.
```

---

## Fase 7 · Evaluaciones, logs y README final
**Concepto:** medir, no adivinar.

**Entregables**
- `evals/run.py` y `evals/dataset.jsonl` (≥ 20 casos, tipos de `docs/07`), partiendo de `evals/dataset.example.jsonl`.
- Resumen de resultados y primera línea base en `docs/09`.
- README final: qué es, arquitectura (diagrama), cómo ejecutarlo, resultados de evaluación, fallos encontrados y lecciones.

**Aceptación**
- `python -m evals.run` produce reporte y código de salida correcto.
- Al menos 3 iteraciones documentadas de "cambio → efecto en la evaluación".
- Un tercero puede levantar el proyecto solo con el README.

**Prompt para Claude Code**
```
Ejecuta la Fase 7 de docs/08-roadmap-fases.md siguiendo docs/07-evaluaciones.md. Amplía
evals/dataset.example.jsonl hasta 20+ casos que cubran todos los tipos listados, incluido
un documento envenenado y un caso de memoria. Implementa el runner y ejecútalo para
obtener la línea base. Muéstrame los fallos y propón (sin aplicar aún) mejoras.
```

---

## Fase 7.B · Búsqueda híbrida (BM25 + vectorial)
**Concepto:** no añadir una pieza sin que los datos la justifiquen. Primero se construyó un dataset difícil (códigos exactos, versiones, parámetros parecidos, paráfrasis) y se midió la recuperación; la vectorial falló en uno; entonces se implementó la híbrida.

**Entregables:** `rag/lexical.py` (BM25 a mano), `rag/hybrid.py` (RRF), `all_chunks()` en los almacenes, `SEARCH_MODE`/`LEXICAL_MIN`, `evals/retrieval.py` (comparación sin LLM), 9 casos `dificil-*` con `kind` y `expect_evidence`, reserva léxica en la fusión (`with_lexical_floor`), ADR-018 y ADR-019.

**Aceptación (cumplida):** `python -m evals.retrieval` compara los tres modos; `hybrid` mejora hit@k en `exact_term` sin bajar otro tipo y sin admitir más fragmentos fuera de alcance; la pasada completa en `hybrid` mantiene el 100 % y la abstención.

**Prueba de uso real (cumplida):** documentación pública de httpx (14 preguntas, 14/14), el manual PDF de `requests` (418 fragmentos), el servidor MCP con Claude Code y el CLI. Encontró un fallo de la fusión RRF con coincidencias exactas fuertes (ADR-019, arreglado con la reserva léxica) y un fallo del CLI con comandos desconocidos. Un PDF sin texto indexa 0 fragmentos con aviso, y uno dañado da un error legible. Detalle en `docs/09`.

---

## Fase 8 · Mejoras guiadas por la prueba de uso real
**Concepto:** cada mejora se justifica con una medición o se descarta con datos.

**Hecho (ver ADR-020 a ADR-023 y las filas de `docs/09`):**
- Progreso en vivo por SSE (`POST /api/chat/stream`, `Agent.run(on_event=…)`): eventos de cada paso, no tokens.
- Skill con divulgación progresiva (`cargar_guia`): −9 % de tokens en diagramas/requisitos y −4 % en preguntas normales sin perder aciertos; es la skill por defecto.
- Validación real de Mermaid con `mermaid-cli`, opcional (`MERMAID_VALIDATE=cli`, instalado en `tools/mermaid/`): rechaza 7 de 7 diagramas que la heurística daba por buenos.
- Ajustes de la skill medidos con el dataset: un diagrama por petición (de 2-4 archivos a 1) y respuestas fuera de alcance breves (mediana ~1.600 → ~780 caracteres).
- `LEXICAL_RESERVE` configurable. Pruebas con documentos reales: web (subida, borrado, errores, SSE) e inyección en un documento real (6/6 sin obedecer).
- La guarda de herramienta nativa **se conserva** (ADR-023): se retiró, el fallo reapareció y se restauró.

**Descartado con datos:**
- *Reranking:* tras la reserva léxica la recuperación acierta en todos los casos; no hay fallo que lo pida.
- *Agente revisor:* sin un fallo medido que lo justifique, duplicaría las llamadas al modelo.
- *Palabras pegadas del PDF:* `pypdf` en modo `layout` no mejora la extracción (27 frente a 23 palabras pegadas en 10 páginas); queda como limitación de la extracción de texto.

**Límites conocidos:** con más de `LEXICAL_RESERVE` fragmentos que comparten un término exacto, alguno puede quedar fuera del top-k; `MERMAID_VALIDATE=cli` necesita Node y Chromium (~170 MB) y, en algunos Linux, `--no-sandbox`.

---

## Extra · Gemini como proveedor alternativo (hecho, ADR-024)
`LLM_PROVIDER=claude|gemini` elige el cliente al arrancar (`core/llm_factory.py`). `GeminiClient` habla con la API REST de Gemini con el mismo protocolo JSON de herramientas, así que el resto del agente no cambia. Con el plan gratuito el modelo por defecto es `gemini-3.5-flash-lite` (500 peticiones al día): 15/15 en la muestra de evaluación, igual que Claude.

## Fase 9 · Separar backend y frontend
**Concepto:** el backend expone una API HTTP y el frontend es una aplicación aparte que solo habla con ella. El refactor cambia la *forma* del código, no su *comportamiento*: los tests existentes son la red de seguridad.

### 9.A · Backend (hecha, ADR-025)
- Todo el código Python se movió a `backend/` con `git mv` (historial conservado); los comandos se ejecutan desde `backend/`.
- `api/main.py` (355 líneas) se dividió en `app.py` (ensamblado), `deps.py` (`Core`, `get_core`), `schemas.py`, `security.py` y `routers/` (chat, conversaciones, documentos, artefactos, salud). `uvicorn techdoc_agent.api.main:app` no cambia.
- Único añadido: CORS con `CORS_ORIGINS` para el frontend.
- **Criterios:** los 597 tests anteriores pasan (solo cambió la ruta de importación de un test y el test de frontera ahora revisa todos los archivos de `api/`) y 5 tests nuevos de CORS; una foto de las 28 respuestas de la API antes y después del refactor coincide (salvo el id aleatorio de los artefactos y la cabecera `Vary` de CORS); CLI, MCP y servidor arrancan; prueba de humo 3/3 con Claude y con Gemini.

### 9.B · Frontend en Next.js (hecha, ADR-026)
Aplicación en `frontend/`: Next.js 16 con shadcn/ui, TanStack Query (estado del servidor), Zustand (estado de la interfaz) y Zod (validación de todo lo que llega de la API). El backend queda como API pura: se retiró `api/static/`. Detalle en `docs/06`, sección C.

**Paridad con la web anterior:**
- [x] Chat con progreso en vivo por SSE (en cola, pensando, cada herramienta con resumen y ms).
- [x] Markdown saneado con botón Copiar en los bloques de código.
- [x] Diagramas Mermaid dibujados (modo estricto) y requisitos en Markdown; artefactos descargables.
- [x] Subir (clic y arrastrar), listar y quitar documentos; errores 413/415/400 legibles.
- [x] Listar, abrir y quitar conversaciones; nueva conversación; la actual se marca.
- [x] Panel de pasos del agente (herramienta, argumentos, duración, error, tokens).
- [x] Enter envía, Shift+Enter añade una línea, tope de 8.000 caracteres.
- [x] Volver a la conversación al recargar (ahora por la URL `/c/<id>` en vez de `localStorage`).
- **Extras:** modo oscuro, *toasts*, diseño responsive (paneles deslizantes en móvil), *skeletons* de carga, estado de la API en la cabecera, confirmación con diálogo en vez de `confirm()`.

**Criterios:** `pnpm lint`, `pnpm typecheck`, `pnpm build`, `pnpm test` (28 tests) y `pnpm e2e` (5 recorridos con el backend real y un LLM guionizado, también con el sistema en modo oscuro, sin errores en la consola) en verde; `pytest` en verde tras retirar la web (601 tests); prueba manual con el modelo real de los dos recorridos (pregunta con cita y diagrama).

### Pulido posterior: auditoría de interfaz (ADR-027)
Revisión del frontend con las skills `better-*` (accesibilidad, layout, textos, tipografía, color y UI) y medición en el navegador: 14 de 15 hallazgos corregidos (6 HIGH), con contraste ≥ 4,5:1 medido en claro y oscuro, foco visible, movimiento reducido y errores que no caducan. E2E: 10 recorridos; Vitest: 29 tests. Queda pendiente mostrar los tipos y el tamaño aceptados antes de subir (la API no los expone).

## Fase 10 · Elegir el proveedor del LLM desde la interfaz (hecha, ADR-028)
**Concepto:** el adaptador elige el `LLMClient` de cada turno y se lo pasa al agente (`Agent.run(..., llm=)`); el núcleo no sabe de dónde viene la elección (regla 2). La API dice qué proveedores hay sin exponer la clave y distingue los errores de disponibilidad.

**Entregables:**
- `Agent.run(..., llm=None)`: todo el turno (también el resumen de memoria) usa ese cliente.
- `LLMUnavailableError` con mensaje para el usuario: falta `GEMINI_API_KEY`, cuota de Gemini agotada (429), CLI de Claude ausente o sin sesión.
- `core/llm_factory`: `build_llm(provider)`, `llm_description(provider)` y `provider_status()`.
- API: `GET /api/providers`, `ChatRequest.provider`, proveedor recordado por conversación, `llm` en cada respuesta y transcripción, 409 (no disponible) y 503 (no se puede usar ahora).
- Interfaz: selector de modelo encima del cuadro de texto e indicación de quién respondió en cada mensaje y en el panel de pasos.
- Decisiones del autor: solo se elige el proveedor (el modelo es el de `.env`) y se puede cambiar en cualquier turno.

**Criterios:**
- [x] Cambiar de proveedor en la web sin reiniciar el servidor; la conversación recuerda el último y una nueva vuelve al de por defecto (E2E).
- [x] `GET /api/providers` nunca contiene la clave (test que la busca).
- [x] Respuesta, transcripción y log (`turn_llm`) registran proveedor y modelo.
- [x] Mensajes claros para cuota, falta de clave y CLI ausente o sin sesión (503 con motivo; 409 si no está disponible).
- [x] CLI, MCP y evaluaciones siguen igual (usan `LLM_PROVIDER`).
- [x] Prueba manual con los dos modelos reales: Claude respondió «concurrencia 4» con cita `[taskflow.md#4]`; tras cambiar a Gemini en la misma conversación, «¿y cómo la cambio a 8?» se respondió con el contexto (`Worker(cola, concurrency=8)`); al recargar seguía Gemini seleccionado.
- [x] Auditoría de lo cambiado (código e interfaz): corregidos el aviso de `Select` no controlado, el desbordamiento a 320 px con un proveedor no disponible, pistas de «sin sesión» demasiado amplias y la ruta local del CLI en `/api/providers`; el E2E falla ahora también con avisos de consola.
- [x] `pytest` 619, Vitest 36, Playwright 12 recorridos, lint, typecheck y build en verde.
