"""Artefactos generados (diagramas y requisitos): listar y descargar, solo dentro de ``outputs/``."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from techdoc_agent import config
from techdoc_agent.api.security import ARTIFACT_NAME
from techdoc_agent.outputs.artifacts import ARTIFACT_TYPES

router = APIRouter()


def artifact_path(name: str) -> Path:
    """Ruta de un artefacto ya validada: nombre permitido y dentro de ``outputs/``."""
    if not ARTIFACT_NAME.fullmatch(name) or ".." in name or Path(name).suffix not in ARTIFACT_TYPES:
        raise HTTPException(400, "Nombre de artefacto no válido")
    base = config.settings.outputs_dir.resolve()
    path = (base / name).resolve()  # resolve() sigue enlaces simbólicos: no pueden sacar de outputs/
    if path.parent != base or not path.is_file():
        raise HTTPException(404, "Artefacto no encontrado")
    return path


def artifact_info(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "name": path.name,
        "type": ARTIFACT_TYPES[path.suffix],
        "size": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(timespec="seconds"),
    }


@router.get("/api/artifacts")
def list_artifacts() -> list[dict[str, Any]]:
    outputs = config.settings.outputs_dir
    if not outputs.is_dir():
        return []
    files = [
        p for p in outputs.iterdir()
        if p.is_file() and ARTIFACT_NAME.fullmatch(p.name) and p.suffix in ARTIFACT_TYPES
    ]
    return [artifact_info(p) for p in sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)]


@router.get("/api/artifacts/{name}")
def download_artifact(name: str) -> FileResponse:
    path = artifact_path(name)
    return FileResponse(path, media_type="text/plain; charset=utf-8", filename=path.name)
