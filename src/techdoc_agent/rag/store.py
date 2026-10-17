"""Interfaz del almacén vectorial y tipos compartidos (ver docs/05).

El agente y la ingesta dependen de esta interfaz, no de una implementación:
``store_json.py`` (Fase 2) y ``store_chroma.py`` (Fase 4) la cumplen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy as np


@dataclass
class Chunk:
    """Fragmento de un documento. ``id`` tiene la forma ``archivo#n`` (n desde 0)."""

    id: str
    source: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchHit:
    chunk: Chunk
    score: float  # similitud coseno: 1 = misma dirección, 0 = sin relación


class VectorStore(Protocol):
    def add(self, chunks: list[Chunk], vectors: np.ndarray) -> None:
        """Guarda fragmentos con sus vectores (una fila por fragmento, normalizados)."""
        ...

    def search(
        self, query_vector: np.ndarray, top_k: int = 5, source: str | None = None
    ) -> list[SearchHit]: ...

    def list_sources(self) -> list[dict[str, Any]]:
        """``[{"source": "taskflow.md", "chunks": 9}, ...]``"""
        ...

    def delete_source(self, source: str) -> int:
        """Elimina todos los fragmentos de un documento; devuelve cuántos."""
        ...

    def count(self) -> int: ...
