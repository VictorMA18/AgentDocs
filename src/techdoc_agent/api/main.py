"""API web (docs/06, sección A): un adaptador delgado sobre el núcleo.

Aquí solo se valida lo que llega por HTTP (mensajes, archivos, nombres) y se delega en el
``Agent``, el ``VectorStore`` y ``ingest_file``. Nada de lógica de agente ni de RAG.
"""

from __future__ import annotations

import json
import os
import queue
import re
import shutil
import tempfile
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from techdoc_agent import config
from techdoc_agent.core.agent import Agent
from techdoc_agent.core.llm import LLMError
from techdoc_agent.core.memory import Memory
from techdoc_agent.core.transcripts import Transcripts
from techdoc_agent.logging_setup import log_event
from techdoc_agent.outputs.artifacts import ARTIFACT_TYPES, turn_artifacts
from techdoc_agent.rag.embeddings import Embedder
from techdoc_agent.rag.ingest import ingest_file
from techdoc_agent.rag.store import VectorStore

STATIC_DIR = Path(__file__).parent / "static"
MAX_MESSAGE_CHARS = 8000
UPLOAD_CHUNK = 1024 * 1024
STREAM_KEEPALIVE_S = 15
MULTIPART_OVERHEAD = 64 * 1024  # margen de cabeceras del multipart al comparar con Content-Length

CONVERSATION_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
SOURCE_NAME = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
ARTIFACT_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]*$")

# Sin scripts inline: la página carga sus propios archivos y las tres librerías fijadas por CDN.
CSP = (
    "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; "
    "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
)


@dataclass
class Core:
    """Piezas del núcleo que usa la API. El candado serializa lo que no es seguro ante hilos."""

    agent: Agent
    store: VectorStore
    embedder: Embedder
    transcripts: Transcripts
    lock: threading.Lock = field(default_factory=threading.Lock)


class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    session_id: str = Field(pattern=r"^[A-Za-z0-9_-]{8,64}$")
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)


def _build_core() -> Core:
    """Construye el núcleo real (carga el modelo de embeddings: tarda unos segundos)."""
    from techdoc_agent.bootstrap import build_agent
    from techdoc_agent.core.llm import ClaudeCliClient
    from techdoc_agent.rag.embeddings import SentenceTransformerEmbedder
    from techdoc_agent.rag.factory import build_store

    embedder, store = SentenceTransformerEmbedder(), build_store()
    agent = build_agent(ClaudeCliClient(), store, embedder, Memory(_conversations_dir()))
    return Core(agent, store, embedder, Transcripts(_conversations_dir()))


# --- validación de nombres ---


def safe_filename(raw: str | None) -> str:
    """Nombre de archivo seguro: sin carpetas, solo ``[A-Za-z0-9._-]``, sin punto inicial, ≤ 100."""
    name = Path((raw or "").replace("\\", "/")).name
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).lstrip(".").strip("-")
    stem, ext = os.path.splitext(name)
    return stem[: 100 - len(ext)] + ext


def _documents_dir() -> Path:
    return config.settings.data_dir / "documents"


def _conversations_dir() -> Path:
    return config.settings.data_dir / "conversations"


def _valid_conversation_id(conversation_id: str) -> str:
    if not CONVERSATION_ID.fullmatch(conversation_id):
        raise HTTPException(400, "Identificador de conversación no válido")
    return conversation_id


def _artifact_path(name: str) -> Path:
    """Ruta de un artefacto ya validada: nombre permitido y dentro de ``outputs/``."""
    if not ARTIFACT_NAME.fullmatch(name) or ".." in name or Path(name).suffix not in ARTIFACT_TYPES:
        raise HTTPException(400, "Nombre de artefacto no válido")
    base = config.settings.outputs_dir.resolve()
    path = (base / name).resolve()  # resolve() sigue enlaces simbólicos: no pueden sacar de outputs/
    if path.parent != base or not path.is_file():
        raise HTTPException(404, "Artefacto no encontrado")
    return path


def _artifact_info(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "name": path.name,
        "type": ARTIFACT_TYPES[path.suffix],
        "size": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(timespec="seconds"),
    }


def _run_turn(core: Core, body: ChatRequest, on_event: Any = None) -> dict[str, Any]:
    """Un turno de chat completo bajo el candado: agente, respuesta documentada y transcripción."""
    with core.lock:
        try:
            result = core.agent.run(body.session_id, body.message, on_event=on_event)
        except LLMError:  # el detalle ya está en el log; al cliente, un mensaje genérico
            raise HTTPException(502, "El modelo no respondió correctamente. Inténtalo de nuevo.") from None
        response = {
            "reply": result.text,
            "tool_calls": [
                {"tool": t.name, "args": t.args, "is_error": t.is_error, "duration_ms": t.duration_ms}
                for t in result.tool_calls
            ],
            "artifacts": turn_artifacts(result.tool_calls, config.settings.outputs_dir),
            "usage": {"input_tokens": result.input_tokens, "output_tokens": result.output_tokens},
            "truncated": result.truncated,
        }
        try:
            core.transcripts.append(body.session_id, {"message": body.message, **response})
        except OSError as exc:  # la respuesta ya existe: no se pierde por un fallo de disco
            log_event(session=body.session_id, event="transcript_save_error", error=str(exc))
    return response


def _sse(event: dict[str, Any]) -> str:
    """Un evento SSE: ``event:`` con el tipo y ``data:`` con el JSON (una sola línea)."""
    return f"event: {event['tipo']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"


def create_app(
    agent: Agent | None = None, store: VectorStore | None = None, embedder: Embedder | None = None
) -> FastAPI:
    """Crea la aplicación. Sin argumentos, el núcleo real se construye al arrancar (lifespan)."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if app.state.core is None:
            app.state.core = _build_core()
        yield

    app = FastAPI(title="TechDoc Agent", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    injected = agent is not None and store is not None and embedder is not None
    app.state.core = Core(agent, store, embedder, Transcripts(_conversations_dir())) if injected else None

    def core_of(request: Request) -> Core:
        return request.app.state.core

    # --- cabeceras de seguridad y tope de subida ---

    @app.middleware("http")
    async def guard(request: Request, call_next: Any) -> Response:
        limit = config.settings.max_upload_mb * 1024 * 1024 + MULTIPART_OVERHEAD
        declared = request.headers.get("content-length", "")
        if request.method == "POST" and request.url.path == "/api/documents" and declared.isdigit() \
                and int(declared) > limit:
            response: Response = JSONResponse(
                {"detail": f"El archivo supera el máximo de {config.settings.max_upload_mb} MB"}, 413)
        else:
            response = await call_next(request)
        response.headers["Content-Security-Policy"] = CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    # --- páginas ---

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/healthz")
    def healthz(request: Request) -> dict[str, Any]:
        core = core_of(request)
        return {"status": "ok", "documents": len(core.store.list_sources()), "chunks": core.store.count()}

    # --- chat ---

    @app.post("/api/chat")
    def chat(body: ChatRequest, request: Request) -> dict[str, Any]:
        return _run_turn(core_of(request), body)

    @app.post("/api/chat/stream")
    def chat_stream(body: ChatRequest, request: Request) -> StreamingResponse:
        """Mismo turno que ``/api/chat`` pero en SSE: eventos de progreso y, al final, ``final`` o ``error``.

        Es progreso, no tokens: la respuesta del modelo llega entera dentro de un JSON estructurado.
        El turno corre en un hilo; si el cliente se desconecta, termina y se guarda igualmente.
        """
        core = core_of(request)
        events: queue.Queue[dict[str, Any] | None] = queue.Queue()

        def work() -> None:
            try:
                if core.lock.locked():  # otro turno en curso: se avisa en vez de dejar al cliente a oscuras
                    events.put({"tipo": "en_cola"})
                events.put({"tipo": "final", **_run_turn(core, body, on_event=events.put)})
            except HTTPException as exc:
                events.put({"tipo": "error", "detalle": exc.detail})
            except Exception as exc:  # noqa: BLE001 - nada de trazas al cliente
                log_event(session=body.session_id, event="stream_error", error=str(exc))
                events.put({"tipo": "error", "detalle": "Error interno del servidor."})
            finally:
                events.put(None)

        threading.Thread(target=work, daemon=True).start()

        def generate() -> Any:
            while True:
                try:
                    event = events.get(timeout=STREAM_KEEPALIVE_S)
                except queue.Empty:
                    yield ": keepalive\n\n"  # un comentario SSE: evita que un proxy cierre la conexión inactiva
                    continue
                if event is None:
                    return
                yield _sse(event)

        return StreamingResponse(generate(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # --- conversaciones guardadas ---

    @app.get("/api/conversations")
    def list_conversations(request: Request) -> list[dict[str, Any]]:
        return core_of(request).transcripts.list()

    @app.get("/api/conversations/{conversation_id}")
    def get_conversation(conversation_id: str, request: Request) -> dict[str, Any]:
        conversation = core_of(request).transcripts.get(_valid_conversation_id(conversation_id))
        if conversation is None:
            raise HTTPException(404, "Conversación no encontrada")
        return conversation

    @app.delete("/api/conversations/{conversation_id}")
    def delete_conversation(conversation_id: str, request: Request) -> dict[str, Any]:
        core = core_of(request)
        with core.lock:
            existed = core.transcripts.delete(_valid_conversation_id(conversation_id))
            core.agent.memory.clear(conversation_id)  # la memoria del agente, en RAM y en disco
        if not existed:
            raise HTTPException(404, "Conversación no encontrada")
        return {"id": conversation_id}

    # --- documentos ---

    @app.get("/api/documents")
    def list_documents(request: Request) -> list[dict[str, Any]]:
        return core_of(request).store.list_sources()

    @app.post("/api/documents", status_code=201)
    def upload_document(request: Request, file: UploadFile = File(...)) -> dict[str, Any]:
        core = core_of(request)
        name = safe_filename(file.filename)
        if not name:
            raise HTTPException(400, "Nombre de archivo no válido")
        if Path(name).suffix.lower() not in config.settings.allowed_extensions:
            raise HTTPException(415, f"Tipo de archivo no permitido: {Path(name).suffix or '(sin extensión)'}")

        max_bytes = config.settings.max_upload_mb * 1024 * 1024
        data = bytearray()
        while chunk := file.file.read(UPLOAD_CHUNK):
            data += chunk
            if len(data) > max_bytes:
                raise HTTPException(413, f"El archivo supera el máximo de {config.settings.max_upload_mb} MB")
        if not data:
            raise HTTPException(400, "El archivo está vacío")

        docs = _documents_dir()
        docs.mkdir(parents=True, exist_ok=True)
        # Se indexa desde una carpeta temporal para no tocar el original si falla; el nombre
        # (y por tanto la fuente de las citas) es el mismo.
        incoming = Path(tempfile.mkdtemp(dir=docs, prefix=".incoming-"))
        try:
            (incoming / name).write_bytes(data)
            with core.lock:
                try:
                    report = ingest_file(incoming / name, core.store, core.embedder)
                except ValueError as exc:
                    raise HTTPException(400, str(exc)) from None
                if report.chunks == 0:
                    (docs / name).unlink(missing_ok=True)  # el índice ya no lo tiene
                    raise HTTPException(400, "El documento no tiene contenido indexable")
                os.replace(incoming / name, docs / name)
        finally:
            shutil.rmtree(incoming, ignore_errors=True)
        return {"source": name, "chunks": report.chunks, "warnings": report.warnings}

    @app.delete("/api/documents/{source}")
    def delete_document(source: str, request: Request) -> dict[str, Any]:
        if not SOURCE_NAME.fullmatch(source) or source.startswith("."):
            raise HTTPException(400, "Nombre de documento no válido")
        core = core_of(request)
        with core.lock:
            removed = core.store.delete_source(source)
            (_documents_dir() / source).unlink(missing_ok=True)
        if removed == 0:
            raise HTTPException(404, "Documento no encontrado")
        return {"source": source, "chunks_removed": removed}

    # --- artefactos ---

    @app.get("/api/artifacts")
    def list_artifacts() -> list[dict[str, Any]]:
        outputs = config.settings.outputs_dir
        if not outputs.is_dir():
            return []
        files = [
            p for p in outputs.iterdir()
            if p.is_file() and ARTIFACT_NAME.fullmatch(p.name) and p.suffix in ARTIFACT_TYPES
        ]
        return [_artifact_info(p) for p in sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)]

    @app.get("/api/artifacts/{name}")
    def download_artifact(name: str) -> FileResponse:
        path = _artifact_path(name)
        return FileResponse(path, media_type="text/plain; charset=utf-8", filename=path.name)

    return app


app = create_app()
