# 03 · Arquitectura

## Principio: un núcleo, dos adaptadores

El agente, el RAG y las herramientas se escriben **una vez** en el núcleo. FastAPI (API para la interfaz web) y MCP (otros clientes) son adaptadores delgados que solo traducen entrada/salida; el frontend Next.js es una aplicación aparte que solo habla con la API.

```mermaid
flowchart TB
    UI["Frontend Next.js<br/>(frontend/, navegador)"]
    subgraph Adaptadores
        WEB["API FastAPI<br/>(JSON + SSE)"]
        MCP["Servidor MCP<br/>(clientes sin interfaz)"]
        CLI["CLI<br/>(desarrollo)"]
    end

    subgraph Nucleo["Núcleo (sin dependencias de web ni MCP)"]
        AG["Agente<br/>(bucle + memoria)"]
        TR["Registro de herramientas"]
        SK["Skill + system prompt"]
        subgraph Tools["Herramientas"]
            T1["buscar_documentos"]
            T2["listar_documentos"]
            T3["generar_diagrama"]
            T4["generar_requisitos"]
        end
    end

    subgraph RAG
        ING["Ingesta<br/>(loaders + chunking)"]
        EMB["Embedder"]
        VS["VectorStore<br/>(JSON → Chroma)"]
    end

    LLM[("CLI de Claude Code<br/>(claude -p)")]
    FS[("data/ · outputs/ · logs/")]

    UI -- HTTP + CORS --> WEB
    WEB --> AG
    MCP --> AG
    MCP --> TR
    CLI --> AG
    AG <--> LLM
    AG --> TR
    SK --> AG
    TR --> T1 & T2 & T3 & T4
    T1 --> VS
    T2 --> VS
    ING --> EMB --> VS
    WEB --> ING
    MCP --> ING
    T3 --> FS
    T4 --> FS
    VS --> FS
```

## Flujo 1 · Un turno de conversación

```mermaid
sequenceDiagram
    actor U as Usuario
    participant A as Adaptador (web/MCP)
    participant AG as Agente
    participant L as LLM
    participant T as Herramienta
    U->>A: "¿Cómo configuro reintentos?"
    A->>AG: run(session_id, mensaje)
    loop hasta respuesta final o tope de iteraciones
        AG->>L: mensajes + herramientas + system prompt
        alt accion = herramientas
            L-->>AG: llamadas(buscar_documentos, query)
            AG->>T: ejecutar(args)
            T-->>AG: resultado o error
            AG->>AG: añade resultado_herramienta al historial
        else accion = responder
            L-->>AG: texto final
        end
    end
    AG-->>A: respuesta + herramientas usadas + artefactos
    A-->>U: respuesta
```

## Flujo 2 · Ingesta de un documento

```mermaid
flowchart LR
    F["Archivo subido"] --> V["Validar<br/>tipo · tamaño · nombre"]
    V --> L["Leer texto<br/>(loader según extensión)"]
    L --> C["Dividir en fragmentos<br/>(con solape)"]
    C --> E["Calcular embeddings"]
    E --> S["Guardar en VectorStore<br/>(texto + vector + metadatos)"]
```

## Flujo 3 · Herramienta con retroalimentación (diagramas)

```mermaid
flowchart LR
    A["LLM escribe código Mermaid"] --> B["generar_diagrama(tipo, titulo, codigo)"]
    B --> C{"¿Sintaxis válida?"}
    C -- Sí --> D["Guarda archivo<br/>devuelve ruta"]
    C -- No --> E["Devuelve errores<br/>(is_error)"]
    E --> A
```

## Decisiones de diseño clave
| Tema | Decisión | Motivo |
|---|---|---|
| Frameworks de agentes | Ninguno | Entender el bucle; evitar cajas negras |
| RAG | Herramienta del agente | El LLM decide cuándo y con qué consulta buscar |
| Almacén vectorial | Interfaz `VectorStore`; JSON+numpy → Chroma | Aprender el mecanismo y luego usar una librería |
| Embeddings | Locales, multilingües | Sin costo ni API key adicional; el contenido suele estar en español |
| Memoria | Por `session_id`; los turnos antiguos se resumen (ADR-011); en disco si el adaptador lo pide (la web, ADR-015) | Controla el contexto enviado en cada llamada y permite retomar una conversación tras reiniciar |
| Frontend | Next.js + TanStack Query + Zustand + Zod + shadcn/ui (Fase 9.B; antes HTML + JS puro) | Aplicación aparte que solo habla con la API; separa estado del servidor y de la interfaz (ADR-026) |
| Diagramas | El LLM escribe Mermaid; la herramienta valida | El feedback de errores permite que el agente se autocorrija |

## Estructura de carpetas
Desde la Fase 9 (ADR-025) el repositorio tiene dos partes: **`backend/`** (todo el código Python: núcleo, RAG, salidas, API, CLI, MCP, tests, evaluaciones, skill y datos) y **`frontend/`** (la interfaz web en Next.js, Fase 9.B, ADR-026; detalle en `docs/06`, sección C). La documentación (`docs/`) y las reglas (`AGENTS.md`) quedan en la raíz. Las rutas de este documento que empiezan por `data/`, `outputs/`, `src/` o `skills/` son relativas a `backend/`. El frontend es otro adaptador más: solo habla con la API HTTP, nunca con el núcleo.

Detalle en `AGENTS.md`, secciones "Mapa de ubicaciones" y "Estructura objetivo".

## Datos en disco
```
data/
  documents/      # archivos originales subidos
  conversations/  # <id>.memory.json (memoria del agente) y <id>.turns.json (lo que muestra la página)
  index/          # índice vectorial (index.json + vectors.npy, o chroma/ según VECTOR_STORE)
outputs/          # diagramas y documentos de requisitos generados
logs/             # agent-YYYYMMDD.jsonl
```
Todo lo anterior va en `.gitignore`, excepto `data/sample_docs/`.
