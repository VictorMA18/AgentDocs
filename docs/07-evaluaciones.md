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

## Resultados (resumen; detalle en `docs/09`)

30 casos × 2 repeticiones, Haiku 5.5, embeddings MiniLM, 4 casos a la vez (≈ 19.000 tokens y 3,6 min por pasada). Cada fila es un cambio y su efecto medido; el detalle está en `docs/09`.

| Pasada | Casos acertados | Tasa media | Lectura |
|---|---|---|---|
| Línea base | 29/30 (97 %) | 95 % | Dos fallos: una regla mal planteada y un «No such tool available» raro |
| 1 · regla de robustez (mencionar ≠ obedecer) | 30/30 | 100 % | Corrección del instrumento (mismas respuestas); el agente no cambió |
| 2 · guarda de herramienta nativa | 30/30 | 100 % | Efecto no medible: el fallo es ≈ 1 de cada 96 ejecuciones |
| 3 · sin el paso «Evalúa la evidencia» | 30/30 | 98 % | La abstención no depende solo de ese paso (hay redundancia con la regla fija) |
| 4a · `MIN_SCORE=0` | 30/30 | 100 % | El umbral no decide la abstención; +4 % de tokens |
| 4b · `MIN_SCORE=0,5` | 29/30 | 93 % | **Regresión**: se pierden fragmentos relevantes (recuperación 97 %, contenido 90 %) |
| 5 · `VECTOR_STORE=chroma` | 30/30 | 100 % | Mismo comportamiento que JSON (tras corregir una frase de la regla de abstención) |

### Búsqueda híbrida (Fase 7.B)

Con 30/30 el dataset ya no discriminaba, así que se añadieron 9 casos difíciles (códigos de error casi idénticos, flags parecidos, dos versiones de una guía, paráfrasis). La búsqueda vectorial falló en uno: el agente dijo que `E-4021` «no aparece en la documentación» estando indexado. Se midió la recuperación **sin gastar tokens** (`python -m evals.retrieval`, 25 casos con evidencia y 7 fuera de alcance):

| Modo | hit@5 | hit@3 | MRR (k=5) | Fragmentos admitidos fuera de alcance |
|---|---|---|---|---|
| `vector` | 24/25 | 20/25 | 0,79 | 22 |
| `lexical` (solo BM25) | 25/25 | 24/25 | 0,95 | 22 |
| `hybrid` (por defecto) | 25/25 | 24/25 | 0,84 | 23 |

La pasada completa en `hybrid` (38 casos × 2) dio 38/38 y `dificil-error-e4021` pasó de 50 % a 100 %. La léxica sola tiene mejor MRR porque las preguntas del dataset repiten palabras del documento, pero falla con paráfrasis; la híbrida es el compromiso seguro. `SEARCH_MODE=vector` restaura el comportamiento anterior. Detalle y calibración de `LEXICAL_MIN` en `docs/09`.

**Prueba de uso real** (`docs/09`): documentación pública de httpx (15 archivos, 14 preguntas: 14/14 correctas), el manual PDF de `requests` (418 fragmentos), el servidor MCP con Claude Code y el CLI. Encontró un fallo que el dataset no veía: con el PDF, la fusión RRF enterraba una coincidencia exacta fuerte (`HTTPAdapter(pool_connections: int = 10, …)`) y el agente decía que no estaba documentada. Se arregló reservando en el top-k los 3 mejores resultados BM25 (ADR-019): 5/5 después, sin cambios en el resto de métricas. También se corrigió que el CLI mandara `/foo` al modelo.

Validación posterior de BM25 (`docs/09`). Con el modelo: la abstención se mantiene (21/21 en `hybrid` y en `vector`, incluidas 4 preguntas con palabras compartidas) y, en 4 casos clave × 5 repeticiones, `hybrid` acierta 20/20 frente al 85 % de `vector` (`E-4021` 5/5 frente a 3/5). Sin tokens: con **Chroma real** da exactamente lo mismo que con JSON; la **búsqueda por palabras exactas no empeora la abstención** (4 preguntas fuera de alcance que comparten palabras con los documentos: 23 fragmentos admitidos frente a 22 de la vectorial, y la propia vectorial ya admite fragmentos en casi todas); el índice BM25 se reconstruye en cada búsqueda, lo que cuesta ≈ 26 ms con 500 fragmentos, ≈ 290 ms con 5.000 y ≈ 1,1 s con 20.000; y `invalidatePrefix` (lowerCamelCase) ahora encuentra `invalidate_prefix`.

Con 2 repeticiones, un 50 % en un caso es una sola ejecución fallida: las diferencias de un punto o dos son ruido. Lo que sí enseñan los datos es que `MIN_SCORE=0,5` perjudica y que la abstención está protegida por varias capas a la vez.

### Proveedores del LLM (ADR-024)

| Muestra de 15 casos × 2 | Aciertos | Tokens por ejecución | Segundos |
|---|---|---|---|
| Claude Haiku 5.5 (CLI) | 15/15 | 16.161 | 11,7 |
| Gemini 3.5 Flash Lite | 15/15 | 6.815 | 9,3 |
| Gemini 3.6 Flash | 5/5 ejecuciones antes de agotar la cuota diaria | ≈ 3-7 mil | 3-8 |

Con el plan gratuito de Gemini conviene `--workers 1`: `gemini-3.6-flash` admite 20 peticiones al día y `gemini-3.5-flash-lite`, 500.
