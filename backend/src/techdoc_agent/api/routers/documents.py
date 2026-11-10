"""Documentos indexados: listar, subir (valida, indexa y guarda) y quitar."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from techdoc_agent import config
from techdoc_agent.api.deps import Core, documents_dir, get_core
from techdoc_agent.api.security import safe_filename, valid_source_name
from techdoc_agent.rag.ingest import ingest_file

UPLOAD_CHUNK = 1024 * 1024

router = APIRouter()


@router.get("/api/documents")
def list_documents(core: Core = Depends(get_core)) -> list[dict[str, Any]]:
    return core.store.list_sources()


@router.post("/api/documents", status_code=201)
def upload_document(file: UploadFile = File(...), core: Core = Depends(get_core)) -> dict[str, Any]:
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

    docs = documents_dir()
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


@router.delete("/api/documents/{source}")
def delete_document(source: str, core: Core = Depends(get_core)) -> dict[str, Any]:
    valid_source_name(source)
    with core.lock:
        removed = core.store.delete_source(source)
        (documents_dir() / source).unlink(missing_ok=True)
    if removed == 0:
        raise HTTPException(404, "Documento no encontrado")
    return {"source": source, "chunks_removed": removed}
