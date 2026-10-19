"""Transcripciones de conversaciones: lo que ve la persona, turno a turno.

Es distinto de la memoria del agente (``memory.py``): aquella guarda el historial en el formato
interno del protocolo y se recorta con resúmenes; esta guarda cada turno ya presentado
(pregunta, respuesta, herramientas, artefactos…) y no se recorta. Un archivo por sesión:
``<session_id>.turns.json``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from techdoc_agent.core.storage import SESSION_ID, check_session_id, quarantine, read_json, write_json_atomic

SUFFIX = ".turns.json"
TITLE_CHARS = 60
MAX_LISTED = 200


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _title(message: str) -> str:
    text = " ".join(message.split())
    return text if len(text) <= TITLE_CHARS else text[: TITLE_CHARS - 1].rstrip() + "…"


def _valid(data: Any) -> bool:
    return (isinstance(data, dict) and isinstance(data.get("title"), str)
            and isinstance(data.get("created"), str) and isinstance(data.get("updated"), str)
            and isinstance(data.get("turns"), list) and all(isinstance(t, dict) for t in data["turns"]))


class Transcripts:
    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)

    def _path(self, session_id: str) -> Path:
        return self.directory / f"{check_session_id(session_id)}{SUFFIX}"

    def _read(self, session_id: str) -> dict[str, Any] | None:
        path = self._path(session_id)
        data = read_json(path)
        if data is None:
            return None
        if not _valid(data):
            quarantine(path, "el contenido no tiene la forma esperada")
            return None
        return data

    def append(self, session_id: str, turn: dict[str, Any]) -> None:
        """Añade un turno; la primera vez crea la conversación con el mensaje como título."""
        now = _now()
        data = self._read(session_id) or {
            "id": session_id, "title": _title(str(turn.get("message", ""))), "created": now, "updated": now,
            "turns": []}
        data["turns"].append({"ts": now, **turn})
        data["updated"] = now
        write_json_atomic(self._path(session_id), data)

    def get(self, session_id: str) -> dict[str, Any] | None:
        data = self._read(session_id)
        return None if data is None else {"id": session_id, **data}

    def list(self) -> list[dict[str, Any]]:
        """Resumen de cada conversación (sin los turnos), las más recientes primero."""
        found = []
        for path in self.directory.glob(f"*{SUFFIX}") if self.directory.is_dir() else []:
            session_id = path.name.removesuffix(SUFFIX)
            if not SESSION_ID.fullmatch(session_id):
                continue
            data = self._read(session_id)
            if data is not None:
                found.append({"id": session_id, "title": data["title"], "updated": data["updated"],
                              "turns": len(data["turns"])})
        return sorted(found, key=lambda c: c["updated"], reverse=True)[:MAX_LISTED]

    def delete(self, session_id: str) -> bool:
        """Borra la conversación; ``False`` si no existía."""
        path = self._path(session_id)
        existed = path.is_file()
        path.unlink(missing_ok=True)
        return existed
