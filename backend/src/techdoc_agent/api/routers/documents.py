"""Documentos de cada conversación (ADR-032): listar, subir (valida, indexa y guarda), quitar y leer
un fragmento citado.

Cada conversación tiene su carpeta (``DATA_DIR/chats/<id>/``) con ``documents/`` e ``index/``: el
agente solo busca en los documentos de la conversación en la que se le pregunta. El índice global
(``DATA_DIR/index``) sigue siendo el de la consola, MCP y las evaluaciones; la web ya no lo usa.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from techdoc_agent import config
from techdoc_agent.api.deps import Core, chat_dir, get_core
from techdoc_agent.api.security import safe_filename, valid_conversation_id, valid_source_name
from techdoc_agent.rag.ingest import ingest_file

UPLOAD_CHUNK = 1024 * 1024
CHUNK_ID = re.compile(r"^(?P<source>[A-Za-z0-9._-]{1,100})#(?P<n>\d{1,6})$")

router = APIRouter()


def _documents(conversation_id: str) -> Path:
    return chat_dir(conversation_id) / "documents"


@router.get("/api/conversations/{conversation_id}/documents")
def list_documents(conversation_id: str, core: Core = Depends(get_core)) -> list[dict[str, Any]]:
    """Documentos de la conversación con su número de fragmentos (vacío si aún no tiene)."""
    conversation_id = valid_conversation_id(conversation_id)
    with core.lock:
        if not core.has_documents(conversation_id):
            return []
        return core.store_for(conversation_id).list_sources()


@router.post("/api/conversations/{conversation_id}/documents", status_code=201)
def upload_document(
    conversation_id: str, file: UploadFile = File(...), core: Core = Depends(get_core)
) -> dict[str, Any]:
    conversation_id = valid_conversation_id(conversation_id)
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

    docs = _documents(conversation_id)
    with core.lock:
        docs.mkdir(parents=True, exist_ok=True)
        # Se indexa desde una carpeta temporal para no tocar el original si falla; el nombre
        # (y por tanto la fuente de las citas) es el mismo.
        incoming = Path(tempfile.mkdtemp(dir=docs, prefix=".incoming-"))
        try:
            (incoming / name).write_bytes(data)
            store = core.store_for(conversation_id)
            try:
                report = ingest_file(incoming / name, store, core.embedder)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from None
            if report.chunks == 0:
                (docs / name).unlink(missing_ok=True)  # el índice ya no lo tiene
                raise HTTPException(400, "El documento no tiene contenido indexable")
            os.replace(incoming / name, docs / name)
        finally:
            shutil.rmtree(incoming, ignore_errors=True)
        # Una conversación nueva existe desde su primer documento: aparece en la lista, sin mensajes y con
        # el nombre del documento como título (el primer mensaje lo sustituye).
        core.transcripts.ensure(conversation_id, title=name)
    return {"source": name, "chunks": report.chunks, "warnings": report.warnings}


@router.delete("/api/conversations/{conversation_id}/documents/{source}")
def delete_document(conversation_id: str, source: str, core: Core = Depends(get_core)) -> dict[str, Any]:
    conversation_id = valid_conversation_id(conversation_id)
    valid_source_name(source)
    with core.lock:
        removed = core.store_for(conversation_id).delete_source(source) if core.has_documents(conversation_id) else 0
        (_documents(conversation_id) / source).unlink(missing_ok=True)
    if removed == 0:
        raise HTTPException(404, "Documento no encontrado")
    return {"source": source, "chunks_removed": removed}


@router.get("/api/conversations/{conversation_id}/documents/{source}")
def get_document(conversation_id: str, source: str, core: Core = Depends(get_core)) -> dict[str, Any]:
    """Vista previa de un documento: sus fragmentos en orden, tal como los indexó el agente (sirve igual
    para un PDF que para un Markdown). Es contenido de un documento: la interfaz lo muestra saneado."""
    conversation_id = valid_conversation_id(conversation_id)
    valid_source_name(source)
    with core.lock:
        chunks = core.store_for(conversation_id).all_chunks(source) if core.has_documents(conversation_id) else []
    if not chunks:
        raise HTTPException(404, "Este documento ya no está en esta conversación. Vuelve a adjuntarlo para verlo.")

    def number(chunk_id: str) -> int:
        tail = chunk_id.rsplit("#", 1)[-1]
        return int(tail) if tail.isdigit() else 0

    ordered = sorted(chunks, key=lambda c: number(c.id))
    return {"source": source, "chunks": [
        {"id": c.id, "n": number(c.id), "section": str(c.metadata.get("section", "")), "text": c.text} for c in ordered]}


@router.get("/api/conversations/{conversation_id}/fragments/{chunk_id}")
def get_fragment(conversation_id: str, chunk_id: str, core: Core = Depends(get_core)) -> dict[str, Any]:
    """Texto de un fragmento citado (``taskflow.md#4``) de los documentos de esa conversación.

    Es contenido de un documento: dato no confiable. La interfaz lo muestra saneado, nunca como HTML.
    """
    conversation_id = valid_conversation_id(conversation_id)
    match = CHUNK_ID.fullmatch(chunk_id)
    if not match:
        raise HTTPException(400, "Identificador de fragmento no válido")
    source = valid_source_name(match["source"])
    with core.lock:
        chunks = core.store_for(conversation_id).all_chunks(source) if core.has_documents(conversation_id) else []
    found = next((c for c in chunks if c.id == chunk_id), None)
    if found is None:
        raise HTTPException(404, "Este fragmento ya no está en los documentos de esta conversación. "
                                 "Vuelve a adjuntar el documento para consultarlo.")
    return {"id": found.id, "source": found.source, "text": found.text}
