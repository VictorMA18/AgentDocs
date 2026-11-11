"""Ensamblado de la aplicación FastAPI: núcleo, middleware y routers (API pura; la interfaz está en frontend/).

La API es un adaptador delgado (docs/06, sección A): aquí solo se valida lo que llega por HTTP y se
delega en el ``Agent``, el ``VectorStore`` e ``ingest_file``. Nada de lógica de agente ni de RAG.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from techdoc_agent import config
from techdoc_agent.api.deps import Core, build_core, conversations_dir
from techdoc_agent.api.routers import artifacts, chat, conversations, documents, health, providers
from techdoc_agent.api.security import add_security_middleware
from techdoc_agent.core.agent import Agent
from techdoc_agent.core.llm import LLMClient
from techdoc_agent.core.transcripts import Transcripts
from techdoc_agent.rag.embeddings import Embedder
from techdoc_agent.rag.store import VectorStore

def create_app(
    agent: Agent | None = None,
    store: VectorStore | None = None,
    embedder: Embedder | None = None,
    llm_factory: Callable[[str], LLMClient] | None = None,
    provider_status: Callable[[], list[dict[str, Any]]] | None = None,
) -> FastAPI:
    """Crea la aplicación. Sin argumentos, el núcleo real se construye al arrancar (lifespan).

    Los tests inyectan el núcleo y, opcionalmente, la factoría de clientes LLM y el estado de los
    proveedores (ADR-028), para no depender de claves ni del CLI de Claude Code.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if app.state.core is None:
            app.state.core = build_core()
        yield

    app = FastAPI(title="TechDoc Agent", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    injected = agent is not None and store is not None and embedder is not None
    app.state.core = Core(agent, store, embedder, Transcripts(conversations_dir())) if injected else None
    if app.state.core is not None:
        # El LLM del agente inyectado atiende al proveedor por defecto (los tests no lanzan el CLI real).
        app.state.core.llms[config.settings.llm_provider] = agent.llm
        if llm_factory is not None:
            app.state.core.llm_factory = llm_factory
        if provider_status is not None:
            app.state.core.provider_status = provider_status

    add_security_middleware(app)
    # CORS se añade después para quedar por fuera: así también las respuestas del guard (p. ej. un 413)
    # llevan sus cabeceras y el frontend puede leer el error. Solo los orígenes de CORS_ORIGINS.
    if config.settings.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=list(config.settings.cors_origins),
                           allow_methods=["GET", "POST", "DELETE"], allow_headers=["Content-Type"])

    for module in (health, chat, conversations, documents, artifacts, providers):
        app.include_router(module.router)
    return app
