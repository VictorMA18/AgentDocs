"""Recuperación: dada una consulta en texto, devuelve los fragmentos más parecidos.

Es deliberadamente fina. El umbral ``MIN_SCORE`` y el formato ``<documento>``
se aplican en la herramienta ``buscar_documentos`` (Fase 3).
"""

from __future__ import annotations

from techdoc_agent import config
from techdoc_agent.rag.embeddings import Embedder
from techdoc_agent.rag.store import SearchHit, VectorStore


def search(
    store: VectorStore,
    embedder: Embedder,
    query: str,
    top_k: int | None = None,
    source: str | None = None,
) -> list[SearchHit]:
    top_k = top_k if top_k is not None else config.settings.top_k_default
    return store.search(embedder.embed_query(query), top_k=top_k, source=source)
