"""Elige el almacén vectorial según ``VECTOR_STORE`` (``json`` o ``chroma``).

El resto del código (agente, ingesta, herramientas) recibe un ``VectorStore`` y no
sabe cuál es. ``chromadb`` se importa solo si se pide Chroma: el modo ``json`` no lo exige.
"""

from __future__ import annotations

from techdoc_agent import config
from techdoc_agent.rag.store import VectorStore

STORES = ("json", "chroma")


def build_store(settings: config.Settings | None = None) -> VectorStore:
    """Abre (o crea) el índice en ``DATA_DIR/index``; Chroma usa la subcarpeta ``chroma``."""
    settings = settings or config.settings
    index_dir = settings.data_dir / "index"
    if settings.vector_store == "json":
        from techdoc_agent.rag.store_json import JsonVectorStore

        return JsonVectorStore(index_dir)
    if settings.vector_store == "chroma":
        from techdoc_agent.rag.store_chroma import ChromaVectorStore

        return ChromaVectorStore(index_dir / "chroma")
    raise ValueError(
        f"VECTOR_STORE='{settings.vector_store}' no es válido; usa uno de: {', '.join(STORES)}"
    )
