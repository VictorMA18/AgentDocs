# 07 · Evaluaciones

Lo que distingue a quien **construye agentes** de quien solo prueba prompts: poder medir si funciona y detectar regresiones.

## Qué se mide
| Métrica | Pregunta que responde | Cómo |
|---|---|---|
| **Uso de herramienta** | ¿Buscó cuando debía y no cuando no debía? | Comparar `tool_calls` con `expect_tools` / `forbid_tools` |
| **Recuperación (hit@k)** | ¿Los fragmentos correctos aparecieron entre los resultados? | `expect_sources` contra las fuentes recuperadas |
| **Contenido** | ¿La respuesta contiene los datos clave? | `must_include` (cadenas) y `must_not_include` |
| **Abstención** | ¿Dijo "no está en la documentación" cuando no estaba? | Casos `out_of_scope: true` + frases de abstención |
| **Citas** | ¿Citó fuentes? | Regex `\[[^\]]+#\d+\]` presente |
| **Artefactos** | ¿El diagrama/requisito se generó y es válido? | Existencia del artefacto y resultado de validación |
| **Robustez** | ¿Resistió inyección en un documento? | Caso con documento envenenado |
| **Costo/latencia** | ¿Cuánto cuesta un caso? | Tokens y ms desde los logs |

Opcional (más avanzado): **LLM como juez** para "groundedness" (¿cada afirmación está respaldada por los fragmentos?). Si se usa, el juez debe ser un prompt aparte, con rúbrica, y se revisa a mano una muestra.

## Formato del dataset (`evals/dataset.jsonl`)
Una línea JSON por caso:

```json
{
  "id": "retry-default",
  "question": "¿Cuántos reintentos hace TaskFlow por defecto?",
  "expect_tools": ["buscar_documentos"],
  "expect_sources": ["taskflow.md"],
  "must_include": ["3"],
  "must_not_include": [],
  "out_of_scope": false,
  "notes": "Dato puntual de la sección Reintentos"
}
```

Campos opcionales: `forbid_tools`, `expect_artifact` (`"mermaid"` | `"requisitos"`), `setup_docs` (documentos extra a indexar para ese caso), `follow_up` (lista de mensajes siguientes en la misma sesión).

## Tipos de casos que debe haber (mínimo 20)
1. Hechos puntuales (valores por defecto, nombres de excepciones).
2. Ejemplos de código ("dame un ejemplo de…").
3. Preguntas que requieren **dos búsquedas** (combinar secciones).
4. Saludo / charla → **sin** herramienta.
5. Fuera de alcance → se abstiene.
6. Generación de diagrama de secuencia, de clases y de flujo.
7. Generación de requisitos desde un documento.
8. Documento envenenado (inyección indirecta).
9. Pregunta ambigua → pide aclaración o declara su suposición.
10. Seguimiento en la misma sesión (memoria).

## Ejecución (`python -m evals.run`)
1. Indexar `data/sample_docs/` en un índice temporal.
2. Para cada caso: ejecutar el agente con una sesión nueva, capturar respuesta, herramientas, artefactos, tokens.
3. Evaluar reglas → `pass`/`fail` por métrica.
4. Escribir `evals/results/YYYYMMDD-HHMM.json` y un resumen en consola (tabla por caso y porcentajes).
5. Salir con código ≠ 0 si el porcentaje global baja del umbral (`EVAL_MIN_PASS`, p. ej. 0.8).

Los modelos no son deterministas: usar temperatura baja y, para decisiones importantes, ejecutar cada caso 2-3 veces y reportar tasa de acierto.

## Cómo usarlo en el desarrollo
- Ejecutarlo **antes y después** de cada cambio importante (chunking, descripción de herramientas, skill, cambio a Chroma).
- Guardar en `docs/09` una tabla de "cambio → efecto en la evaluación". Esa tabla es oro para el portafolio.
- Cada fallo real que encuentres → conviértelo en un caso nuevo.
