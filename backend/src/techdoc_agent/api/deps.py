"""Dependencias compartidas por los routers: el núcleo (``Core``) y las carpetas de datos."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import Request

from techdoc_agent import config
from techdoc_agent.core.agent import Agent
from techdoc_agent.core.memory import Memory
from techdoc_agent.core.transcripts import Transcripts
from techdoc_agent.rag.embeddings import Embedder
from techdoc_agent.rag.store import VectorStore


@dataclass
class Core:
    """Piezas del núcleo que usa la API. El candado serializa lo que no es seguro ante hilos."""

    agent: Agent
    store: VectorStore
    embedder: Embedder
    transcripts: Transcripts
    lock: threading.Lock = field(default_factory=threading.Lock)


def documents_dir() -> Path:
    return config.settings.data_dir / "documents"


def conversations_dir() -> Path:
    return config.settings.data_dir / "conversations"


def build_core() -> Core:
    """Construye el núcleo real (carga el modelo de embeddings: tarda unos segundos)."""
    from techdoc_agent.bootstrap import build_agent
    from techdoc_agent.core.llm_factory import build_llm
    from techdoc_agent.rag.embeddings import SentenceTransformerEmbedder
    from techdoc_agent.rag.factory import build_store

    embedder, store = SentenceTransformerEmbedder(), build_store()
    agent = build_agent(build_llm(), store, embedder, Memory(conversations_dir()))
    return Core(agent, store, embedder, Transcripts(conversations_dir()))


def get_core(request: Request) -> Core:
    """Dependencia de FastAPI: el núcleo creado al arrancar (o inyectado en los tests)."""
    return request.app.state.core
