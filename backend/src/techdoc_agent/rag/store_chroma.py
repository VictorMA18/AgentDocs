"""Almacén vectorial con ChromaDB (índice HNSW persistente en disco).

Cumple la misma interfaz ``VectorStore`` que ``store_json.py``. Los vectores los
calcula nuestro ``Embedder`` (el de Chroma es solo inglés), así que la colección se
crea sin función de embeddings. Chroma devuelve *distancias*; con coseno,
``score = 1 - distancia``, la misma escala que el producto punto del almacén JSON.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import chromadb
import numpy as np
from chromadb.config import Settings
from chromadb.errors import InvalidArgumentError

from techdoc_agent.rag.store import Chunk, SearchHit

COLLECTION = "chunks"
SOURCE_KEY = "source"  # el origen viaja en los metadatos de Chroma para poder filtrar


class ChromaVectorStore:
    def __init__(self, index_dir: str | Path) -> None:
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(self.index_dir), settings=Settings(anonymized_telemetry=False)
        )
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION,
            configuration={"hnsw": {"space": "cosine"}},
            embedding_function=None,
        )

    def _dimension(self) -> int | None:
        """Dimensión de los vectores guardados (``None`` si el índice está vacío)."""
        if self._collection.count() == 0:
            return None
        got = self._collection.get(limit=1, include=["embeddings"])
        return len(got["embeddings"][0])

    # --- interfaz VectorStore ---

    def add(self, chunks: list[Chunk], vectors: np.ndarray) -> None:
        vectors = np.asarray(vectors, dtype=np.float32)
        if vectors.ndim != 2 or vectors.shape[0] != len(chunks):
            raise ValueError(
                f"Se esperaba una matriz con {len(chunks)} filas, se recibió {vectors.shape}"
            )
        if not chunks:
            return
        dimension = self._dimension()
        if dimension is not None and vectors.shape[1] != dimension:
            raise ValueError(
                f"Dimensión {vectors.shape[1]} distinta de la del índice ({dimension}): "
                "¿se cambió el modelo de embeddings? Reindexa los documentos."
            )

        # ``upsert`` (no ``add``): un id repetido sustituye al anterior, como en el JSON.
        step = self._client.get_max_batch_size()
        for start in range(0, len(chunks), step):
            batch = chunks[start : start + step]
            self._collection.upsert(
                ids=[c.id for c in batch],
                embeddings=vectors[start : start + step].tolist(),
                documents=[c.text for c in batch],
                metadatas=[{**c.metadata, SOURCE_KEY: c.source} for c in batch],
            )

    def search(
        self, query_vector: np.ndarray, top_k: int = 5, source: str | None = None
    ) -> list[SearchHit]:
        total = self._collection.count()
        if total == 0 or top_k <= 0:
            return []
        query = np.asarray(query_vector, dtype=np.float32)
        dimension = self._dimension()
        if query.shape != (dimension,):
            raise ValueError(f"El vector de consulta debe tener forma ({dimension},)")

        try:
            result = self._collection.query(
                query_embeddings=[query.tolist()],
                n_results=min(top_k, total),
                where={SOURCE_KEY: source} if source is not None else None,
                include=["documents", "metadatas", "distances"],
            )
        except InvalidArgumentError as exc:  # p. ej. una dimensión que no encaja
            raise ValueError(str(exc)) from exc
        hits = []
        for id_, text, metadata, distance in zip(
            result["ids"][0], result["documents"][0], result["metadatas"][0],
            result["distances"][0], strict=True,
        ):
            origin = metadata.pop(SOURCE_KEY)
            hits.append(SearchHit(Chunk(id_, origin, text, metadata), 1.0 - float(distance)))
        return hits

    def all_chunks(self, source: str | None = None) -> list[Chunk]:
        result = self._collection.get(
            where={SOURCE_KEY: source} if source is not None else None, include=["documents", "metadatas"]
        )
        chunks = []
        for id_, text, metadata in zip(result["ids"], result["documents"], result["metadatas"], strict=True):
            metadata = dict(metadata)
            chunks.append(Chunk(id_, metadata.pop(SOURCE_KEY), text, metadata))
        return chunks

    def list_sources(self) -> list[dict[str, Any]]:
        metadatas = self._collection.get(include=["metadatas"])["metadatas"]
        counts = Counter(m[SOURCE_KEY] for m in metadatas)
        return [{"source": s, "chunks": n} for s, n in counts.items()]

    def delete_source(self, source: str) -> int:
        ids = self._collection.get(where={SOURCE_KEY: source}, include=[])["ids"]
        if ids:
            self._collection.delete(ids=ids)
        return len(ids)

    def count(self) -> int:
        return self._collection.count()
