# 08 · Roadmap por fases

Estado (marca al terminar cada una):

- [x] Fase 0 · Preparación
- [x] Fase 1 · Bucle del agente con herramienta falsa
- [x] Fase 2 · Ingesta + almacén JSON (sin agente)
- [x] Fase 3 · RAG como herramienta + skill
- [ ] Fase 3b · Herramientas de diagramas y requisitos
- [ ] Fase 4 · Migración a ChromaDB
- [ ] Fase 5 · FastAPI + HTML
- [ ] Fase 6 · Servidor MCP
- [ ] Fase 7 · Evaluaciones, logs y README final
- [ ] Fase 8 · (Opcional) streaming, agente revisor (la memoria recortada ya se adelantó, ver ADR-011)

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
- `mcp_server.py` con `FastMCP`, herramientas de `docs/06` (sección B), transporte stdio, logs a stderr.
- Documentar en el README cómo conectarlo a Claude Code y a Claude Desktop.
- Test con el cliente MCP del SDK.

**Aceptación**
- `claude mcp add techdoc -- python -m techdoc_agent.mcp_server` y, desde Claude Code, "lista mis documentos" usa tu servidor.
- `ingestar_documento` rechaza rutas fuera de `ALLOWED_INGEST_DIR`.
- `mcp_server.py` no duplica lógica del núcleo.

**Prompt para Claude Code**
```
Ejecuta la Fase 6 de docs/08-roadmap-fases.md siguiendo docs/06-api-y-mcp.md (sección
B). Usa el SDK oficial de Python de MCP (FastMCP) y transporte stdio. Nada de print a
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

## Fase 8 · Opcional
- Streaming SSE en la web.
- ~~Recorte/resumen de historial~~ (hecho tras la Fase 3, ADR-011).
- Skill con divulgación progresiva (`cargar_skill`).
- Agente revisor que critique la respuesta del primero (workflow evaluador-optimizador).
- Búsqueda híbrida y reranking, validados con las evaluaciones.
- Validación real de Mermaid con `mermaid-cli`.
