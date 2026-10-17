"""Embeddings: interfaz ``Embedder`` y su implementación local multilingüe.

Un embedding es un vector que representa el significado de un texto. Se
guardan **normalizados** (norma 1): así la similitud coseno es un producto punto.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np

from techdoc_agent import config


class Embedder(Protocol):
    dimension: int

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        """Matriz ``(len(texts), dimension)`` de vectores normalizados."""
        ...

    def embed_query(self, text: str) -> np.ndarray:
        """Vector normalizado de forma ``(dimension,)``."""
        ...


def normalize(vectors: np.ndarray) -> np.ndarray:
    """Divide cada vector por su norma (los vectores nulos se dejan en cero)."""
    norms = np.linalg.norm(vectors, axis=-1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return (vectors / norms).astype(np.float32)


class SentenceTransformerEmbedder:
    """Modelo local de ``sentence-transformers`` (multilingüe por defecto, corre en CPU).

    La primera ejecución descarga el modelo (~470 MB). Se importa la librería
    dentro del constructor para que los tests no carguen PyTorch.
    """

    def __init__(self, model_name: str | None = None) -> None:
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name or config.settings.embedding_model
        self._model = SentenceTransformer(self.model_name)
        self.dimension: int = int(self._model.get_embedding_dimension())

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dimension), dtype=np.float32)
        vectors = self._model.encode(
            texts, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False
        )
        return normalize(vectors)

    def embed_query(self, text: str) -> np.ndarray:
        return self.embed_documents([text])[0]
