"""Dependencias compartidas por los routers: el núcleo (``Core``) y las carpetas de datos."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import Request

from techdoc_agent import config
from techdoc_agent.core.agent import Agent
from techdoc_agent.core.llm import LLMClient
from techdoc_agent.core.llm_factory import build_llm, provider_status
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
    # Proveedores del LLM (ADR-028): cada cliente se crea la primera vez que se pide y se reutiliza.
    # Los tests inyectan una factoría y un estado falsos para no depender de claves ni del CLI.
    llm_factory: Callable[[str], LLMClient] = build_llm
    provider_status: Callable[[], list[dict[str, Any]]] = provider_status
    llms: dict[str, LLMClient] = field(default_factory=dict)

    def get_llm(self, provider: str) -> LLMClient:
        """Cliente del proveedor (llamar con el candado tomado)."""
        if provider not in self.llms:
            self.llms[provider] = self.llm_factory(provider)
        return self.llms[provider]


def documents_dir() -> Path:
    return config.settings.data_dir / "documents"


def conversations_dir() -> Path:
    return config.settings.data_dir / "conversations"


def build_core() -> Core:
    """Construye el núcleo real (carga el modelo de embeddings: tarda unos segundos)."""
    from techdoc_agent.bootstrap import build_agent
    from techdoc_agent.rag.embeddings import SentenceTransformerEmbedder
    from techdoc_agent.rag.factory import build_store

    embedder, store = SentenceTransformerEmbedder(), build_store()
    default = build_llm()  # el de LLM_PROVIDER: lo usa el agente si un turno no elige otro
    agent = build_agent(default, store, embedder, Memory(conversations_dir()))
    core = Core(agent, store, embedder, Transcripts(conversations_dir()))
    core.llms[config.settings.llm_provider] = default
    return core


def get_core(request: Request) -> Core:
    """Dependencia de FastAPI: el núcleo creado al arrancar (o inyectado en los tests)."""
    return request.app.state.core
