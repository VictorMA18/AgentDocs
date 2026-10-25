"""Recuperación: dada una consulta en texto, devuelve los fragmentos más parecidos.

Es deliberadamente fina. Los umbrales ``MIN_SCORE`` y ``LEXICAL_MIN`` y el formato ``<documento>``
se aplican en la herramienta ``buscar_documentos`` (Fase 3).

Tres modos (``SEARCH_MODE``): ``vector`` (significado, el de siempre), ``lexical`` (BM25, palabras
exactas; sobre todo para comparar) e ``hybrid`` (ambos fusionados con RRF, Fase 7.B). Los hits
conservan siempre la similitud coseno en ``score``, así ``MIN_SCORE`` significa lo mismo en los tres.
"""

from __future__ import annotations

from techdoc_agent import config
from techdoc_agent.rag.embeddings import Embedder
from techdoc_agent.rag.hybrid import rrf_fuse
from techdoc_agent.rag.lexical import Bm25Index
from techdoc_agent.rag.store import SearchHit, VectorStore

SEARCH_MODES = ("vector", "lexical", "hybrid")


def search(
    store: VectorStore,
    embedder: Embedder,
    query: str,
    top_k: int | None = None,
    source: str | None = None,
    mode: str | None = None,
) -> list[SearchHit]:
    top_k = top_k if top_k is not None else config.settings.top_k_default
    mode = mode or config.settings.search_mode
    if mode not in SEARCH_MODES:
        raise ValueError(f"modo de búsqueda desconocido: {mode!r} (válidos: {', '.join(SEARCH_MODES)})")
    query_vector = embedder.embed_query(query)
    if mode == "vector":
        return store.search(query_vector, top_k=top_k, source=source)

    # Con BM25 hace falta el coseno de todos los fragmentos para conservarlo en ``score``.
    total = store.count()
    cosine = {h.chunk.id: h.score for h in store.search(query_vector, top_k=total, source=source)}
    lexical = Bm25Index(store.all_chunks(source)).search(query, top_k=total)
    bm25 = {chunk.id: score for chunk, score in lexical}
    if mode == "lexical":
        ids = [chunk.id for chunk, _ in lexical][:top_k]
    else:
        by_cosine = sorted(cosine, key=lambda id_: -cosine[id_])
        ids = [id_ for id_, _ in rrf_fuse([by_cosine, [chunk.id for chunk, _ in lexical]])][:top_k]
    chunks = {c.id: c for c in store.all_chunks(source)}
    return [SearchHit(chunks[id_], cosine.get(id_, 0.0), bm25.get(id_, 0.0)) for id_ in ids]
