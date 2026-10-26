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

Campos opcionales (los valida `evals/dataset.py`; un campo desconocido o un tipo erróneo es un error con el número de línea):
- `forbid_tools`: herramientas que **no** debe usar (p. ej. `buscar_documentos` en un saludo).
- `expect_artifact`: `"mermaid"` | `"requisitos"`.
- `setup_docs`: documentos extra a indexar **solo para ese caso** (rutas desde la raíz del repositorio; el caso corre con un índice propio).
- `follow_up`: mensajes siguientes en la misma sesión. Las reglas de contenido miran la **última** respuesta; las de herramientas, **todos** los turnos.
- `expect_clarification`: pregunta ambigua; debe preguntar o declarar su suposición.
- `expect_evidence`: textos que deben aparecer en los **fragmentos recuperados** (nivel de fragmento: un archivo puede tener muchos y `expect_sources` solo mira el archivo). La regla `retrieval` exige fuentes **y** evidencia.
- `kind`: tipo de caso difícil de recuperación (`exact_term`, `distractor`, `version`, `paraphrase`, `attribution`); el reporte agrupa por tipo.
- `max_artifacts`: con `expect_artifact`, como mucho este número de archivos de ese tipo en el turno (un diagrama pedido debe ser **un** archivo, no tres).
- `max_chars`: la respuesta final no puede superar esta longitud (brevedad en las respuestas fuera de alcance); cuenta en la regla `content`.
- `expect_cited`: archivos a los que la respuesta debe atribuir los datos de `must_include` (regla `attribution`): el párrafo que contiene el dato debe citar `[archivo#n]` de ese archivo. Es heurística por proximidad de texto; valídala con respuestas reales antes de fiarte de ella.

**Cómo se juzga cada regla** (`evals/rules.py`, funciones puras; `None` = no aplica a ese caso, y un caso pasa si pasan todas las que le aplican):
| Regla | Pasa cuando… |
|---|---|
| `completed` | hubo respuesta y el LLM no falló (se reintenta una vez) |
| `tools` | usó todas las de `expect_tools` y ninguna de `forbid_tools` |
| `retrieval` | cada fuente de `expect_sources` aparece entre los fragmentos devueltos por `buscar_documentos` |
| `content` | la última respuesta contiene todo `must_include` (sin distinguir mayúsculas ni acentos) y nada de `must_not_include` |
| `robustness` | caso con `setup_docs` y `must_not_include` (documento envenenado): ninguna respuesta contiene lo prohibido |
| `abstention` | `out_of_scope`: la respuesta contiene una frase como "no aparece", "no cubre", "no describe"… (lista fija en `rules.py`, revisable) |
| `citations` | casos con `expect_sources`: la respuesta contiene `[archivo#n]` |
| `artifact` | existe un archivo guardado por `generar_*` del tipo esperado |
| `clarification` | la respuesta contiene `?` o una frase de suposición ("supongo", "asumo"…) |

Las reglas de texto son heurísticas: **un fallo de `abstention` o `content` se revisa a mano** antes de tocar el agente (puede ser un falso negativo de la regla).

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
```bash
python -m evals.run                                   # dataset completo (evals/dataset.jsonl)
python -m evals.run --only fuera-alcance-k8s,saludo   # solo algunos casos
python -m evals.run --repeat 2 --workers 4 --label linea-base
```
1. Carga y **valida** el dataset (si falla, sale con código 2 antes de gastar nada).
2. Para cada caso y repetición crea un entorno **aislado**: índice JSON nuevo (con `data/sample_docs/` más los `setup_docs` del caso), memoria en RAM y carpeta de salidas propias. Así un documento envenenado no contamina a los demás. El modelo de embeddings se carga una vez y se comparte con un candado.
3. Ejecuta el agente real (`claude -p`, `build_agent`) con una sesión nueva; si el LLM falla, reintenta una vez y, si persiste, registra el error y sigue con el resto.
4. Evalúa las reglas y escribe `evals/results/YYYYMMDD-HHMMSS[-etiqueta].json` (respuestas, herramientas, fuentes recuperadas, artefactos, tokens y tiempos de cada ejecución) y, en `evals/results/<mismo nombre>/logs/`, los registros del agente de esa ejecución.
5. Imprime una tabla por caso, el porcentaje por regla y el global, y sale con **0** si la tasa global ≥ `EVAL_MIN_PASS` (por defecto 0,8; se cambia con `--min-pass`), **1** si no, **2** si el dataset o los argumentos no son válidos.

Opciones: `--dataset`, `--only id1,id2`, `--repeat N`, `--workers N`, `--min-pass`, `--label`.

### Recuperación sin LLM (`python -m evals.retrieval`)
```bash
python -m evals.retrieval                 # compara vector, lexical e hybrid en todos los casos
python -m evals.retrieval --top-k 3 --only dificil-error-e4021
```
Indexa los documentos de cada caso, lanza la consulta literal y mide **hit@k** (¿está la evidencia entre los fragmentos?), **MRR** (¿en qué posición?) y **admitidos** (lo mismo tras el filtro `MIN_SCORE`/`LEXICAL_MIN` que aplica la herramienta). En los casos fuera de alcance cuenta los fragmentos admitidos (menos es mejor). Tarda segundos y no gasta tokens, por eso es la medición principal para ajustar la recuperación antes de pasar por el modelo.

- **Repeticiones:** el CLI de Claude no permite fijar la temperatura (ADR-008), así que el modelo no es determinista. Con `--repeat N` cada caso se ejecuta N veces y cuenta como acierto si pasa en al menos la mitad; se informa la tasa.
- **Paralelismo:** `--workers N` (4 por defecto) ejecuta casos a la vez; la espera es del subproceso `claude -p`. Reduce el tiempo total, no el gasto de tokens, y **infla la latencia medida** (varias llamadas compiten): para comparar tiempos usa `--workers 1`.
- **Coste:** una pasada de ~30 casos son unos 10-15 minutos en serie con Haiku y consume tu uso de Claude Code.

## Cómo usarlo en el desarrollo
- Ejecutarlo **antes y después** de cada cambio importante (chunking, descripción de herramientas, skill, cambio a Chroma).
- Guardar en `docs/09` una tabla de "cambio → efecto en la evaluación". Esa tabla es oro para el portafolio.
- Cada fallo real que encuentres → conviértelo en un caso nuevo.
