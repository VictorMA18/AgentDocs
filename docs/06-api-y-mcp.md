# 06 · API web (FastAPI) y servidor MCP

Ambos son **adaptadores delgados**: validan entrada, llaman al núcleo, formatean salida. Ninguna lógica de agente ni de RAG vive aquí.

## A. FastAPI

### Endpoints
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/` | Sirve `static/index.html` |
| GET | `/healthz` | `{"status":"ok","documents":N,"chunks":M}` |
| POST | `/api/chat` | Cuerpo: `{"session_id": "...", "message": "..."}` |
| POST | `/api/documents` | Subida `multipart/form-data` (campo `file`) |
| GET | `/api/documents` | Lista de documentos indexados |
| DELETE | `/api/documents/{source}` | Elimina un documento del índice |
| GET | `/api/artifacts` | Lista de artefactos generados |
| GET | `/api/artifacts/{name}` | Descarga un artefacto (nombre validado) |

### Códigos de estado
| Código | Cuándo |
|---|---|
| 201 | Documento subido e indexado (`{"source", "chunks", "warnings"}`) |
| 400 | Nombre no válido, archivo vacío o sin contenido indexable, nombre de artefacto o de documento con formato incorrecto |
| 404 | Documento o artefacto inexistente (también rutas con `..` o enlaces simbólicos que salen de `outputs/`) |
| 413 | Archivo mayor que `MAX_UPLOAD_MB` |
| 415 | Extensión fuera de `ALLOWED_EXTENSIONS` |
| 422 | Cuerpo de `/api/chat` inválido (`session_id` con `^[A-Za-z0-9_-]{8,64}$`, mensaje de 1 a 8.000 caracteres) |
| 502 | El LLM falló; el mensaje es genérico y el detalle va al log |

### Respuesta de `/api/chat`
```json
{
  "reply": "Para configurar reintentos... [taskflow.md#3]",
  "tool_calls": [
    {"tool": "buscar_documentos", "args": {"query": "configurar reintentos"}, "is_error": false, "duration_ms": 41}
  ],
  "artifacts": [{"name": "diagrama-encolar-3f2a.mmd", "type": "mermaid", "title": "Encolar y procesar"}],
  "usage": {"input_tokens": 2410, "output_tokens": 312},
  "truncated": false
}
```

`artifacts` lista los archivos que `generar_diagrama` y `generar_requisitos` guardaron **en ese turno**: el nombre sale del resultado de la herramienta (`ToolTrace.result`), el título de sus argumentos y el tipo de la extensión (`.mmd` → `mermaid`, `.md` → `requirements`). `GET /api/artifacts` devuelve `name`, `type`, `size` y `modified` de todos los archivos válidos de `outputs/`.

### Interfaz (`static/`)
Una sola página (`index.html`, con `app.js` y `app.css` propios: sin scripts inline para poder usar una CSP estricta), JS puro con `fetch`:
- Panel izquierdo: subir documento, lista de documentos (con botón eliminar).
- Centro: chat. Los bloques de código con botón "copiar". Los artefactos Mermaid se **renderizan** con la librería `mermaid` (cargada por CDN con versión fija).
- Panel derecho (plegable): "Qué hizo el agente" → herramientas y argumentos del turno.
- `session_id` aleatorio guardado en `sessionStorage`.
- Markdown renderizado con una librería pequeña (p. ej. `marked`) **sanitizando** el HTML (p. ej. `DOMPurify`) — la salida del modelo no es confiable.

### Reglas
- Límite de tamaño de subida (`MAX_UPLOAD_MB`) y lista blanca de extensiones. Se rechaza antes de leer el cuerpo si `Content-Length` ya lo supera (mejor esfuerzo: sin esa cabecera, el servidor puede haber recibido parte del archivo) y se aborta durante la lectura al pasar el límite.
- Nombre de archivo **saneado** (ADR-014): sin carpetas, solo `[A-Za-z0-9._-]`, sin punto inicial, hasta 100 caracteres. No se genera uno nuevo porque ese nombre es la fuente de las citas (`[archivo#n]`); subir el mismo nombre reemplaza el documento. Se guarda en `data/documents/`.
- `GET /api/artifacts/{name}`: solo `^[a-z0-9][a-z0-9._-]*$` con extensión `.mmd` o `.md`, sin `..`, resuelto dentro de `outputs/` (un enlace simbólico que salga se rechaza). Se sirve como `text/plain` con `Content-Disposition: attachment`.
- CORS cerrado por defecto (mismo origen). Cabeceras en todas las respuestas: `Content-Security-Policy` (scripts solo propios y de `cdn.jsdelivr.net`), `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`. `/docs`, `/redoc` y `/openapi.json` están desactivados.
- Un único candado serializa chat, subida y borrado (la memoria y el almacén JSON no son seguros ante hilos). Pensado para un usuario local; con varios usuarios habría que usar un candado por sesión.
- (Opcional Fase 8) `POST /api/chat/stream` con SSE.

### Cómo arrancar
```bash
uvicorn techdoc_agent.api.main:app --reload     # http://127.0.0.1:8000
```
Al arrancar carga el modelo de embeddings y abre el almacén según `VECTOR_STORE`. `create_app(agent, store, embedder)` permite inyectar un núcleo falso en los tests (`tests/api/`).

## B. Servidor MCP

### Qué es MCP aquí
Un protocolo estándar para que **otros clientes** (Claude Desktop, Claude Code, otro agente) usen tus herramientas sin pasar por tu interfaz web. Se implementa con el SDK oficial de Python (`FastMCP`).

### Herramientas expuestas
| Herramienta MCP | Qué hace | ¿Usa LLM interno? |
|---|---|---|
| `buscar_documentos(query, top_k, source)` | Búsqueda directa en el índice | No |
| `listar_documentos()` | Documentos indexados | No |
| `ingestar_documento(ruta)` | Indexa un archivo local (ruta validada contra directorio permitido) | No |
| `preguntar_agente(pregunta, session_id)` | Ejecuta el agente completo y devuelve la respuesta | **Sí** |

Reflexión de diseño (anótala en `docs/09`): exponer `buscar_documentos` permite que el LLM **del cliente** haga su propio razonamiento con tu RAG; `preguntar_agente` entrega un agente completo como caja negra. Ambos tienen sentido; el primero es más barato y componible.

### Transporte
- **stdio** (por defecto): el cliente lanza el proceso. **Nunca imprimir en stdout** (rompe el protocolo); logs a stderr.
- **HTTP** (opcional, después): para acceso remoto, con autenticación.

### Configuración de clientes
Claude Code:
```bash
claude mcp add techdoc -- python -m techdoc_agent.mcp_server
```
Claude Desktop (`claude_desktop_config.json`), con rutas absolutas:
```json
{
  "mcpServers": {
    "techdoc": {
      "command": "/ruta/al/proyecto/.venv/bin/python",
      "args": ["-m", "techdoc_agent.mcp_server"]
    }
  }
}
```
Verificar la sintaxis vigente en la documentación oficial de MCP antes de codificar.

### Pruebas
- Test automático: instanciar el servidor y llamar las herramientas con el cliente del SDK.
- Prueba manual: el inspector de MCP (`npx @modelcontextprotocol/inspector`) o conectarlo a Claude Code y pedir "lista mis documentos".

### Seguridad MCP
- `ingestar_documento` solo acepta rutas dentro de `ALLOWED_INGEST_DIR`.
- Describir bien cada herramienta (es lo que el cliente lee para decidir).
- Tratar los argumentos como no confiables, igual que en la web.
