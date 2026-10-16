# 02 · Requisitos

Prioridad según MoSCoW: **M**ust, **S**hould, **C**ould. Cada requisito tiene un criterio de aceptación verificable.

## Requisitos funcionales

| ID | Requisito | Prior. | Criterio de aceptación |
|---|---|---|---|
| RF-01 | El sistema permite subir documentos (.md, .txt, .pdf, código) | M | Subir un archivo válido lo deja listado y buscable |
| RF-02 | Los documentos se dividen en fragmentos con metadatos (fuente, posición) | M | Cada fragmento recuperado indica archivo y número de fragmento |
| RF-03 | El agente dispone de la herramienta `buscar_documentos` y decide cuándo usarla | M | Ante un saludo no busca; ante una pregunta técnica sí |
| RF-04 | El agente puede hacer varias búsquedas en un mismo turno con consultas distintas | M | Visible en los logs en preguntas complejas |
| RF-05 | Las respuestas citan la fuente (archivo + fragmento) | M | Toda afirmación técnica va con cita `[archivo#n]` |
| RF-06 | Si la información no está en los documentos, el agente lo declara | M | Caso "fuera de alcance" del dataset pasa |
| RF-07 | Los ejemplos de código se basan en lo recuperado, no se inventan APIs | M | Evaluación de "groundedness" ≥ umbral |
| RF-08 | El agente puede generar diagramas Mermaid validados | M | Sintaxis válida; si falla, el agente se corrige |
| RF-09 | El agente puede generar un documento de requisitos estructurado | M | Ids únicos, prioridad y criterio de aceptación presentes |
| RF-10 | Los artefactos generados se guardan y se pueden descargar | S | `GET /api/artifacts/{nombre}` devuelve el archivo |
| RF-11 | Existe historial de conversación por sesión | M | El agente recuerda el turno anterior |
| RF-12 | El comportamiento del agente se define con una skill (`SKILL.md`) | M | Cambiar la skill cambia el formato de salida sin tocar código |
| RF-13 | Interfaz web de chat con subida de documentos | M | Flujo completo desde el navegador |
| RF-14 | Servidor MCP expone el agente y sus herramientas | M | Un cliente MCP lista y llama las herramientas |
| RF-15 | Se pueden listar y eliminar documentos del índice | S | Tras eliminar, ya no aparece en búsquedas |
| RF-16 | Se puede cambiar de almacén vectorial por configuración | S | `VECTOR_STORE=json\|chroma` sin otros cambios |
| RF-17 | Respuesta en streaming en la web | C | Los tokens aparecen progresivamente |
| RF-18 | Mostrar en la interfaz qué herramientas usó el agente | S | Panel con herramientas y argumentos por turno |

## Requisitos no funcionales

| ID | Categoría | Requisito | Métrica / criterio |
|---|---|---|---|
| RNF-01 | Seguridad | La API key solo vive en variables de entorno | Ninguna clave en el repo (revisión con búsqueda) |
| RNF-02 | Seguridad | Los documentos se tratan como datos, no como instrucciones | Caso de inyección del dataset pasa |
| RNF-03 | Seguridad | Validación de subidas: tipo, tamaño, nombre seguro | Rechaza `../x`, ejecutables y archivos > límite |
| RNF-04 | Robustez | El bucle tiene tope de iteraciones | Nunca excede `MAX_AGENT_ITERATIONS` |
| RNF-05 | Robustez | Errores de herramienta se devuelven al modelo, no rompen el bucle | Herramienta que lanza excepción → `is_error` y el agente continúa |
| RNF-06 | Observabilidad | Cada paso queda registrado en JSONL | Hay log con herramienta, args, duración y tokens |
| RNF-07 | Mantenibilidad | Núcleo desacoplado de FastAPI y MCP | `core/` y `rag/` no importan `api/` ni `mcp_server` |
| RNF-08 | Mantenibilidad | Cobertura de tests de la lógica del núcleo | Tests de chunking, store, herramientas y bucle (con LLM simulado) |
| RNF-09 | Rendimiento | Búsqueda sobre ≤ 10 000 fragmentos | < 200 ms (sin contar embedding de la consulta) |
| RNF-10 | Costo | Embeddings locales, sin servicio de pago | No requiere otra API key |
| RNF-11 | Portabilidad | Se instala con `pip install -r requirements.txt` | Arranca en una máquina limpia siguiendo el README |
| RNF-12 | Idioma | Responde en el idioma del usuario (español por defecto) | Caso de evaluación en español |
