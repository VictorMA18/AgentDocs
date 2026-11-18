"""Dependencias compartidas por los routers: el núcleo (``Core``) y las carpetas de datos."""

from __future__ import annotations

import shutil
import threading
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import Request

from techdoc_agent import config
from techdoc_agent.core.agent import Agent
from techdoc_agent.core.llm import LLMClient
from techdoc_agent.core.llm_factory import build_llm, provider_status
from techdoc_agent.bootstrap import ToolRegistry, conversation_tools
from techdoc_agent.core.memory import Memory
from techdoc_agent.core.transcripts import Transcripts
from techdoc_agent.rag.embeddings import Embedder
from techdoc_agent.rag.store import VectorStore

OPEN_STORES = 8  # almacenes de conversación abiertos a la vez (los demás se reabren al usarlos)


@dataclass
class Core:
    """Piezas del núcleo que usa la API. El candado serializa lo que no es seguro ante hilos.

    ``store`` es el índice global (el de la consola, MCP y las evaluaciones; lo cuenta /healthz). La web
    usa un índice por conversación (ADR-032): ``store_for`` lo abre y ``tools_for`` da al agente las
    herramientas RAG atadas a él para ese turno.
    """

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
    stores: OrderedDict[str, VectorStore] = field(default_factory=OrderedDict)

    def get_llm(self, provider: str) -> LLMClient:
        """Cliente del proveedor (llamar con el candado tomado)."""
        if provider not in self.llms:
            self.llms[provider] = self.llm_factory(provider)
        return self.llms[provider]

    def store_for(self, conversation_id: str) -> VectorStore:
        """Índice de una conversación (llamar con el candado tomado y el id ya validado). Se guardan
        abiertos los últimos ``OPEN_STORES``."""
        from techdoc_agent.rag.factory import build_store

        if conversation_id in self.stores:
            self.stores.move_to_end(conversation_id)
        else:
            self.stores[conversation_id] = build_store(index_dir=chat_dir(conversation_id) / "index")
            if len(self.stores) > OPEN_STORES:
                self.stores.popitem(last=False)
        return self.stores[conversation_id]

    def has_documents(self, conversation_id: str) -> bool:
        """¿Tiene índice propio? Sin él no se abre (ni se crea) nada en disco."""
        return (chat_dir(conversation_id) / "index").is_dir()

    def tools_for(self, conversation_id: str) -> ToolRegistry:
        """Herramientas del agente para un turno: las RAG buscan solo en los documentos de esa conversación."""
        return conversation_tools(self.agent, self.store_for(conversation_id), self.embedder)

    def forget(self, conversation_id: str) -> None:
        """Cierra el índice de la conversación y borra sus documentos (llamar con el candado tomado)."""
        self.stores.pop(conversation_id, None)
        shutil.rmtree(chat_dir(conversation_id), ignore_errors=True)


def documents_dir() -> Path:
    """Documentos del índice global (los indexa la consola; la web ya no sube aquí)."""
    return config.settings.data_dir / "documents"


def chats_dir() -> Path:
    return config.settings.data_dir / "chats"


def chat_dir(conversation_id: str) -> Path:
    """Carpeta de una conversación: ``documents/`` (los archivos subidos) e ``index/`` (su índice)."""
    return chats_dir() / conversation_id


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
