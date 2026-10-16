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
- `PersistentClient(path="data/index/chroma")`, una colección, `metric: cosine`.
- Se le pasan los embeddings calculados por nuestro `Embedder`.
- Filtro por fuente con `where={"source": ...}`. Recordar que Chroma devuelve **distancias**; convertir a score (`1 - distancia` en coseno).
- Verificar la API vigente en la documentación de Chroma antes de codificar.

### Migración (Fase 4)
Mismo conjunto de pruebas parametrizado para ambos almacenes (`@pytest.mark.parametrize`). Comparar resultados del dataset de evaluación antes y después y **anotarlo** en `docs/09` (buena historia de portafolio).

## Recuperación

- `top_k` por defecto 5; el agente puede pedir más.
- Umbral mínimo de score configurable (`MIN_SCORE`, p. ej. 0.25). Por debajo, el fragmento se descarta; si no queda ninguno, `"Sin resultados relevantes"`.
- Cada resultado se formatea como:
```
<documento fuente="taskflow.md" fragmento="3" seccion="Reintentos" score="0.82">
...texto...
</documento>
```

## Mejoras posibles (después de v1, guiadas por evaluación)
1. Búsqueda híbrida (BM25 + vectorial).
2. *Reranking* con un modelo cruzado.
3. Reescritura de consulta (el propio agente ya lo hace al reformular).
4. Deduplicación de fragmentos casi idénticos.
5. Chunking consciente de la estructura (AST para código).
