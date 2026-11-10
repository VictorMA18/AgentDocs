"""Frontera de seguridad de la API: cabeceras, tope de subida y validación de nombres.

Todo lo que llega por HTTP y se usa como nombre de archivo o identificador pasa por aquí antes de
tocar el disco o el núcleo (docs/06, sección A; ADR-014).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from techdoc_agent import config

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


def add_security_middleware(app: FastAPI) -> None:
    """Cabeceras de seguridad en cada respuesta y rechazo temprano (413) de subidas demasiado grandes."""

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


def safe_filename(raw: str | None) -> str:
    """Nombre de archivo seguro: sin carpetas, solo ``[A-Za-z0-9._-]``, sin punto inicial, ≤ 100."""
    name = Path((raw or "").replace("\\", "/")).name
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).lstrip(".").strip("-")
    stem, ext = os.path.splitext(name)
    return stem[: 100 - len(ext)] + ext


def valid_conversation_id(conversation_id: str) -> str:
    if not CONVERSATION_ID.fullmatch(conversation_id):
        raise HTTPException(400, "Identificador de conversación no válido")
    return conversation_id


def valid_source_name(source: str) -> str:
    if not SOURCE_NAME.fullmatch(source) or source.startswith("."):
        raise HTTPException(400, "Nombre de documento no válido")
    return source
