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

### Respuesta de `/api/chat`
```json
{
  "reply": "Para configurar reintentos... [taskflow.md#3]",
  "tool_calls": [
    {"tool": "buscar_documentos", "args": {"query": "configurar reintentos"}, "is_error": false, "duration_ms": 41}
  ],
  "artifacts": [{"name": "diagrama-secuencia-3f2a.mmd", "type": "mermaid", "title": "Encolar y procesar"}],
  "usage": {"input_tokens": 2410, "output_tokens": 312},
  "truncated": false
}
```

### Interfaz (`static/index.html`)
Una sola página, JS puro con `fetch`:
- Panel izquierdo: subir documento, lista de documentos (con botón eliminar).
- Centro: chat. Los bloques de código con botón "copiar". Los artefactos Mermaid se **renderizan** con la librería `mermaid` (cargada por CDN con versión fija).
- Panel derecho (plegable): "Qué hizo el agente" → herramientas y argumentos del turno.
- `session_id` aleatorio guardado en `sessionStorage`.
- Markdown renderizado con una librería pequeña (p. ej. `marked`) **sanitizando** el HTML (p. ej. `DOMPurify`) — la salida del modelo no es confiable.

### Reglas
- Límite de tamaño de subida (`MAX_UPLOAD_MB`) y lista blanca de extensiones.
- Nombre de archivo guardado = generado; el original solo se conserva como metadato.
- `GET /api/artifacts/{name}`: aceptar solo `^[a-z0-9._-]+$` y resolver dentro de `outputs/`.
- CORS cerrado por defecto (mismo origen).
- (Opcional Fase 8) `POST /api/chat/stream` con SSE.

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
