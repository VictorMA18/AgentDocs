# 01 · Visión y alcance

## Problema
Al trabajar en proyectos de software, la documentación (de librerías, de APIs, notas propias, requisitos antiguos) está dispersa. Encontrar el dato correcto, obtener un ejemplo de código fiable o convertir lo que se sabe en diagramas y requisitos formales consume tiempo.

## Solución
Un **agente conversacional** que:
1. Mantiene un índice de los documentos que el usuario le entrega.
2. **Decide** cuándo y qué buscar en ese índice (el RAG es una herramienta suya).
3. Responde citando la fuente y con ejemplos de código basados en la documentación.
4. Genera **artefactos** (diagramas Mermaid, documentos de requisitos) validados y descargables.
5. Se comporta según una **skill** (`SKILL.md`) que define método, formatos y tono.

## Usuarios
- **Primario:** el autor (estudiante/desarrollador) documentando proyectos propios.
- **Secundario:** otros clientes que consuman el agente vía **MCP** (Claude Desktop, Claude Code, otro agente), sin interfaz.

## Objetivos de aprendizaje (lo que el proyecto debe demostrar)
| # | Concepto | Dónde se practica |
|---|---|---|
| 1 | Bucle de agente con *tool use* | Fase 1 |
| 2 | RAG: chunking, embeddings, búsqueda por similitud | Fase 2 |
| 3 | RAG como herramienta (el LLM decide) | Fase 3 |
| 4 | Abstracción de almacenes vectoriales | Fase 4 |
| 5 | Herramientas que **validan** y devuelven feedback al modelo | Fase 3b |
| 6 | Exponer el mismo núcleo por HTTP y por MCP | Fases 5-6 |
| 7 | Evaluación sistemática y observabilidad | Fase 7 |
| 8 | Seguridad básica de agentes (inyección, límites) | Transversal |

## Dentro del alcance (v1)
- Ingesta de `.md`, `.txt`, `.pdf` y archivos de código (`.py`, `.js`, `.ts`, `.java`, `.json`, `.yaml`).
- Chat con historial por sesión.
- Herramientas: `buscar_documentos`, `listar_documentos`, `generar_diagrama`, `generar_requisitos`.
- Diagramas Mermaid: clases, secuencia, componentes/flujo, entidad-relación, estados.
- Interfaz web simple (FastAPI + HTML) y servidor MCP.
- Evaluaciones automáticas y logs.

## Fuera del alcance (v1)
- Autenticación/multiusuario real.
- Despliegue en producción y escalado.
- Ejecutar el código generado.
- Crawling automático de sitios web.
- Fine-tuning de modelos.
- Frameworks de agentes.

## Criterio de éxito
- Responde correctamente ≥ 80 % del dataset de evaluación (ver `docs/07`).
- Cuando la respuesta **no está** en los documentos, lo dice en lugar de inventar.
- Los diagramas generados pasan validación de sintaxis ≥ 90 % de las veces.
- El autor puede explicar de memoria el bucle, el RAG y la arquitectura.

## Ideas para después de v1
- Un segundo agente revisor que critique al primero.
- Búsqueda híbrida (BM25 + vectorial) y *reranking*.
- Persistencia de conversaciones.
- Streaming de respuestas por SSE.
- Ingesta desde una URL o repositorio.
