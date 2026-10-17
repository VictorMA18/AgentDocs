"""Almacén vectorial en disco: ``index.json`` (fragmentos) + ``vectors.npy`` (vectores).

Es una "base vectorial" mínima para entender qué hace una de verdad: guarda
vectores normalizados y busca con un producto matricial. Las filas de
``vectors.npy`` están alineadas con la lista de fragmentos de ``index.json``.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from techdoc_agent.rag.store import Chunk, SearchHit


class JsonVectorStore:
    def __init__(self, index_dir: str | Path) -> None:
        self.index_dir = Path(index_dir)
        self._chunks: list[Chunk] = []
        self._vectors = np.zeros((0, 0), dtype=np.float32)
        self._dimension: int | None = None
        self._load()

    @property
    def _index_path(self) -> Path:
        return self.index_dir / "index.json"

    @property
    def _vectors_path(self) -> Path:
        return self.index_dir / "vectors.npy"

    # --- persistencia ---

    def _load(self) -> None:
        if not self._index_path.exists() or not self._vectors_path.exists():
            return
        data = json.loads(self._index_path.read_text(encoding="utf-8"))
        self._chunks = [Chunk(**c) for c in data["chunks"]]
        self._dimension = int(data["dimension"])
        self._vectors = np.load(self._vectors_path)
        if self._vectors.shape != (len(self._chunks), self._dimension):
            raise ValueError(
                f"Índice corrupto en {self.index_dir}: {len(self._chunks)} fragmentos "
                f"y vectores de forma {self._vectors.shape}. Reindexa los documentos."
            )

    def _save(self) -> None:
        """Escribe a archivos temporales y los renombra (evita dejar un archivo a medias)."""
        self.index_dir.mkdir(parents=True, exist_ok=True)
        tmp_vectors = self._vectors_path.with_suffix(".npy.tmp")
        tmp_index = self._index_path.with_suffix(".json.tmp")
        with tmp_vectors.open("wb") as fh:
            np.save(fh, self._vectors)
        payload: dict[str, Any] = {
            "dimension": self._dimension,
            "chunks": [
                {"id": c.id, "source": c.source, "text": c.text, "metadata": c.metadata}
                for c in self._chunks
            ],
        }
        tmp_index.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp_vectors, self._vectors_path)
        os.replace(tmp_index, self._index_path)

    # --- interfaz VectorStore ---

    def add(self, chunks: list[Chunk], vectors: np.ndarray) -> None:
        vectors = np.asarray(vectors, dtype=np.float32)
        if vectors.ndim != 2 or vectors.shape[0] != len(chunks):
            raise ValueError(
                f"Se esperaba una matriz con {len(chunks)} filas, se recibió {vectors.shape}"
            )
        if not chunks:
            return
        if self._dimension is None:
            self._dimension = vectors.shape[1]
        elif vectors.shape[1] != self._dimension:
            raise ValueError(
                f"Dimensión {vectors.shape[1]} distinta de la del índice ({self._dimension}): "
                "¿se cambió el modelo de embeddings? Reindexa los documentos."
            )

        # Un id repetido sustituye al anterior.
        new_ids = {c.id for c in chunks}
        keep = np.array([c.id not in new_ids for c in self._chunks], dtype=bool)
        kept_vectors = self._vectors[keep] if len(self._chunks) else np.zeros((0, self._dimension), np.float32)
        self._chunks = [c for c, k in zip(self._chunks, keep, strict=True) if k] + list(chunks)
        self._vectors = np.vstack([kept_vectors, vectors])
        self._save()

    def search(
        self, query_vector: np.ndarray, top_k: int = 5, source: str | None = None
    ) -> list[SearchHit]:
        if not self._chunks or top_k <= 0:
            return []
        query = np.asarray(query_vector, dtype=np.float32)
        if query.shape != (self._dimension,):
            raise ValueError(f"El vector de consulta debe tener forma ({self._dimension},)")

        scores = self._vectors @ query  # coseno, porque todos están normalizados
        candidates = np.arange(len(self._chunks))
        if source is not None:
            candidates = np.array(
                [i for i, c in enumerate(self._chunks) if c.source == source], dtype=int
            )
        order = candidates[np.argsort(-scores[candidates], kind="stable")][:top_k]
        return [SearchHit(self._chunks[i], float(scores[i])) for i in order]

    def list_sources(self) -> list[dict[str, Any]]:
        counts = Counter(c.source for c in self._chunks)
        return [{"source": s, "chunks": n} for s, n in counts.items()]

    def delete_source(self, source: str) -> int:
        keep = np.array([c.source != source for c in self._chunks], dtype=bool)
        removed = int((~keep).sum())
        if removed:
            self._chunks = [c for c, k in zip(self._chunks, keep, strict=True) if k]
            self._vectors = self._vectors[keep]
            self._save()
        return removed

    def count(self) -> int:
        return len(self._chunks)
