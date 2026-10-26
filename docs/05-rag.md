# 05 · RAG

## Conceptos en 1 minuto
- **Embedding:** lista de números (vector) que representa el significado de un texto. Textos parecidos → vectores cercanos.
- **Almacén vectorial:** guarda `(texto, vector, metadatos)` y, dado el vector de una consulta, devuelve los más cercanos.
- **Similitud coseno:** mide el ángulo entre vectores (1 = idénticos en dirección, 0 = sin relación).
- **Chunking:** dividir documentos en fragmentos del tamaño justo para que cada uno tenga sentido por sí solo.

## Ingesta

```
archivo → validar → leer texto → dividir → embeddings → guardar
```

### Loaders (`rag/loaders.py`)
| Extensión | Estrategia |
|---|---|
| `.md`, `.txt` | Leer UTF-8 |
| `.pdf` | Extraer texto por página (`pypdf`); advertir si no hay texto (PDF escaneado) |
| `.py .js .ts .java .json .yaml .yml` | Leer como texto; marcar `lenguaje` en metadatos |

### Chunking (`rag/chunking.py`)
Empezar simple y mejorar con evidencia (evaluaciones), no por intuición.

- **Texto/Markdown:** dividir por encabezados (`#`, `##`) y, si una sección es larga, por párrafos; objetivo ~500-800 caracteres (≈150-250 tokens), **solape** ~100 caracteres.
- **Código:** dividir por funciones/clases si es posible; si no, por bloques de ~40 líneas con solape de 5.
- **Bloques de código dentro de Markdown:** no partirlos por la mitad; mantenerlos con el párrafo que los introduce.
- Cada fragmento lleva el **encabezado de su sección** como prefijo (mejora mucho la recuperación).

Los ids son `archivo#n` con **n desde 0** (`taskflow.md#0`, `#1`…). Si el tamaño exacto choca con un bloque de código atómico, gana el bloque: `chunk_size` es aproximado.

Metadatos por fragmento:
```json
{"id": "taskflow.md#3", "source": "taskflow.md", "chunk_index": 3,
 "section": "Reintentos", "type": "md", "text": "..."}
```

### Embeddings (`rag/embeddings.py`)
Interfaz:
```python
class Embedder(Protocol):
    dimension: int
    def embed_documents(self, texts: list[str]) -> np.ndarray: ...
    def embed_query(self, text: str) -> np.ndarray: ...
```
Implementación por defecto: `sentence-transformers` con un modelo **multilingüe** (p. ej. `paraphrase-multilingual-MiniLM-L12-v2`), configurable con `EMBEDDING_MODEL`. Se descarga la primera vez y corre en CPU.

> Nota: el modelo por defecto de ChromaDB es solo-inglés. Como la documentación suele estar en español, se le pasa **siempre nuestro `Embedder`** y no se usa el embedding por defecto de Chroma.

Normalizar los vectores (norma 1) al guardarlos: así la similitud coseno es un simple producto punto.

## Almacén vectorial

### Interfaz (`rag/store.py`)
```python
@dataclass
class Chunk: id: str; source: str; text: str; metadata: dict

@dataclass
class SearchHit: chunk: Chunk; score: float

class VectorStore(Protocol):
    def add(self, chunks: list[Chunk], vectors: np.ndarray) -> None: ...
    def search(self, query_vector: np.ndarray, top_k: int = 5,
               source: str | None = None) -> list[SearchHit]: ...
    def list_sources(self) -> list[dict]: ...      # [{"source":..., "chunks": n}]
    def delete_source(self, source: str) -> int: ...
    def count(self) -> int: ...
```

### Opción A · JSON + numpy (Fase 2)
- Persistencia: `data/index/index.json` (chunks y metadatos) + `data/index/vectors.npy`.
- Búsqueda: `scores = vectors @ query_vector`; `np.argsort(-scores)[:top_k]`.
- ~30-60 líneas. Sirve para **entender** qué hace una base vectorial.
- Límite práctico: decenas de miles de fragmentos.

### Opción B · ChromaDB (Fase 4)
`rag/store_chroma.py` → `ChromaVectorStore(index_dir)`; API verificada con `chromadb` 1.5.9:
- `chromadb.PersistentClient(path=…, settings=Settings(anonymized_telemetry=False))` y una colección `chunks` creada con `get_or_create_collection(name, configuration={"hnsw": {"space": "cosine"}}, embedding_function=None)`: se le pasan **siempre** los vectores de nuestro `Embedder` (el embedding por defecto de Chroma es solo inglés).
- Guardado con `upsert(ids, embeddings, documents, metadatas)`. `add` ignora en silencio los ids repetidos; `upsert` los reemplaza (como el almacén JSON). Se trocea según `client.get_max_batch_size()`.
- El origen viaja en los metadatos (`source`) para poder filtrar con `where={"source": …}`; al reconstruir el `Chunk` se retira, así `chunk.metadata` es idéntico al del JSON. Los metadatos de Chroma solo admiten str/int/float/bool.
- Chroma devuelve **distancias**; con coseno, `score = 1 - distancia` (misma escala que el producto punto del JSON; diferencia medida ≤ 2·10⁻⁷). `n_results` mayor que el número de elementos se recorta solo.
- Una dimensión distinta lanza `InvalidArgumentError`; el almacén la traduce al mismo `ValueError` ("Reindexa los documentos") que el JSON.
- Ruta: `data/index/chroma/` (convive con `index.json` + `vectors.npy`).

### Selección del almacén (`rag/factory.py`)
`build_store()` lee `VECTOR_STORE` (`json` por defecto, o `chroma`) y devuelve un `VectorStore`. `cli.py` e `ingest.py` lo usan; el agente y las herramientas solo ven la interfaz. `chromadb` se importa únicamente si se elige Chroma. **No hay migración automática**: al cambiar de almacén (como al cambiar de modelo de embeddings) hay que reindexar con `/ingestar`.

### Migración (Fase 4)
Los tests del almacén son un contrato parametrizado (`tests/rag/test_store_contract.py`) que corre contra ambas implementaciones; además hay un test de paridad (mismo corpus → mismos fragmentos y scores). La comparación medida (resultados, latencia, tamaño) está en `docs/09` (ADR-013).

## Recuperación

`rag/retrieval.py` expone `search(store, embedder, query, top_k, source)`: embebe la consulta y busca. No aplica umbral ni formato; eso lo hace la herramienta `buscar_documentos` (`core/tools_rag.py`, Fase 3).

Prueba por consola (Fase 2):
```bash
python -m techdoc_agent.rag.ingest data/sample_docs --buscar "reintentos"   # indexa y busca
python -m techdoc_agent.rag.ingest --buscar "reintentos" --top-k 3           # solo busca (usa el índice guardado)
```
El índice guarda la dimensión de los vectores; si cambias `EMBEDDING_MODEL` hay que reindexar (el almacén rechaza dimensiones distintas).

- `top_k` por defecto 5; el agente puede pedir más.
- Umbral mínimo de score configurable (`MIN_SCORE`, p. ej. 0.25). Por debajo, el fragmento se descarta; si no queda ninguno, `"Sin resultados relevantes"`. En los modos léxico e híbrido también pasa un fragmento con coincidencia de palabras muy fuerte (`LEXICAL_MIN`, BM25 ≥ 4,0 por defecto) aunque su coseno no llegue a `MIN_SCORE`.
- **Modo de búsqueda** (`SEARCH_MODE`, Fase 7.B, ADR-018): `hybrid` (por defecto) fusiona la búsqueda vectorial y BM25 con RRF; `vector` es la de siempre (solo significado); `lexical` es solo BM25 y existe sobre todo para comparar. `rag/lexical.py` implementa BM25 a mano (minúsculas, sin acentos; conserva `E-4021` y `ack_batch_window` enteros y partidos, y parte el lowerCamelCase `invalidatePrefix` pero no el PascalCase `TaskFlow`) y `rag/hybrid.py` la fusión por posición `1/(60+posición)`. El índice léxico se reconstruye en memoria a partir de `VectorStore.all_chunks()` en cada búsqueda: cuesta ≈ 26 ms con 500 fragmentos, ≈ 290 ms con 5.000 y ≈ 1,1 s con 20.000; con muchos más habría que cachearlo. `SearchHit.score` es siempre el coseno y `lexical_score` el BM25 (`None` en `vector`). Como RRF solo mira posiciones y puede enterrar una coincidencia exacta muy fuerte, los `LEXICAL_RESERVE` (3 por defecto; 0 = RRF pura) mejores resultados BM25 por encima de `LEXICAL_MIN` entran siempre en el top-k (`with_lexical_floor`, ADR-019).
- Cada resultado se formatea como:
```
<documento fuente="taskflow.md#3" seccion="Reintentos" score="0.82">
...texto...
</documento>
```

## Mejoras posibles (después de v1, guiadas por evaluación)
1. ~~Búsqueda híbrida (BM25 + vectorial).~~ Hecha en la Fase 7.B (ADR-018).
2. *Reranking* con un modelo cruzado.
3. Reescritura de consulta (el propio agente ya lo hace al reformular).
4. Deduplicación de fragmentos casi idénticos.
5. Chunking consciente de la estructura (AST para código).
