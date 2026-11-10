"""Ensamblado de la aplicación FastAPI: núcleo, middleware, páginas y routers.

La API es un adaptador delgado (docs/06, sección A): aquí solo se valida lo que llega por HTTP y se
delega en el ``Agent``, el ``VectorStore`` e ``ingest_file``. Nada de lógica de agente ni de RAG.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from techdoc_agent import config
from techdoc_agent.api.deps import Core, build_core, conversations_dir
from techdoc_agent.api.routers import artifacts, chat, conversations, documents, health
from techdoc_agent.api.security import add_security_middleware
from techdoc_agent.core.agent import Agent
from techdoc_agent.core.transcripts import Transcripts
from techdoc_agent.rag.embeddings import Embedder
from techdoc_agent.rag.store import VectorStore

STATIC_DIR = Path(__file__).parent / "static"


def create_app(
    agent: Agent | None = None, store: VectorStore | None = None, embedder: Embedder | None = None
) -> FastAPI:
    """Crea la aplicación. Sin argumentos, el núcleo real se construye al arrancar (lifespan)."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if app.state.core is None:
            app.state.core = build_core()
        yield

    app = FastAPI(title="TechDoc Agent", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    injected = agent is not None and store is not None and embedder is not None
    app.state.core = Core(agent, store, embedder, Transcripts(conversations_dir())) if injected else None

    add_security_middleware(app)
    # CORS se añade después para quedar por fuera: así también las respuestas del guard (p. ej. un 413)
    # llevan sus cabeceras y el frontend puede leer el error. Solo los orígenes de CORS_ORIGINS.
    if config.settings.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=list(config.settings.cors_origins),
                           allow_methods=["GET", "POST", "DELETE"], allow_headers=["Content-Type"])

    # --- páginas (web estática; se retira cuando el frontend Next.js tenga paridad) ---

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    for module in (health, chat, conversations, documents, artifacts):
        app.include_router(module.router)
    return app
