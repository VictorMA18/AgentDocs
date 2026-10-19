"""Utilidades de archivos JSON por sesión, compartidas por la memoria y las transcripciones.

El ``session_id`` forma parte del nombre del archivo, así que se valida antes de usarlo en una
ruta. Las escrituras son atómicas y un archivo ilegible se aparta (``.corrupt``) en vez de
romper la conversación.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from techdoc_agent.logging_setup import log_event

SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def check_session_id(session_id: str) -> str:
    """Devuelve el id si es seguro como parte de un nombre de archivo; si no, ``ValueError``."""
    if not SESSION_ID.fullmatch(session_id):
        raise ValueError(f"session_id no válido (solo letras, números, '-' y '_', máximo 64): {session_id!r}")
    return session_id


def write_json_atomic(path: Path, data: Any) -> None:
    """Escribe a un temporal y lo renombra: nunca queda un archivo a medias."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def read_json(path: Path) -> Any | None:
    """Lee un JSON; ``None`` si no existe o no se puede leer (en ese caso lo aparta)."""
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        quarantine(path, str(exc))
        return None


def quarantine(path: Path, reason: str) -> None:
    """Aparta un archivo inservible como ``<nombre>.corrupt`` y lo registra."""
    log_event(event="storage_load_error", file=path.name, error=reason)
    try:
        os.replace(path, path.with_name(path.name + ".corrupt"))
    except OSError:
        pass
