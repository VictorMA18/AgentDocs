"""Transcripciones de conversaciones: lo que ve la persona, turno a turno.

Es distinto de la memoria del agente (``memory.py``): aquella guarda el historial en el formato
interno del protocolo y se recorta con resúmenes; esta guarda cada turno ya presentado
(pregunta, respuesta, herramientas, artefactos…) y no se recorta. Un archivo por sesión:
``<session_id>.turns.json``.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from techdoc_agent.core.llm import undo_double_escape
from techdoc_agent.core.storage import SESSION_ID, check_session_id, quarantine, read_json, write_json_atomic

SUFFIX = ".turns.json"
TITLE_CHARS = 60
MAX_TITLE_CHARS = 120  # título puesto a mano (renombrar)
MAX_QUERY_CHARS = 100  # búsqueda de conversaciones
SNIPPET_CHARS = 90
_MARKDOWN = re.compile(r"[`*#>|]+")  # marcas de Markdown que ensucian el fragmento (no «_»: va en identificadores)
MAX_LISTED = 200


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _title(message: str) -> str:
    text = " ".join(message.split())
    return text if len(text) <= TITLE_CHARS else text[: TITLE_CHARS - 1].rstrip() + "…"


def _fold(text: str) -> tuple[str, list[int]]:
    """Texto sin tildes y en minúsculas, con la posición original de cada carácter (para el fragmento)."""
    folded, positions = [], []
    for i, char in enumerate(text):
        for part in unicodedata.normalize("NFD", char).casefold():
            if not unicodedata.combining(part):
                folded.append(part)
                positions.append(i)
    return "".join(folded), positions


def _snippet(text: str, query: str) -> str | None:
    """Trozo de ~90 caracteres alrededor de la primera aparición de ``query`` (ya plegada), o ``None``."""
    clean = " ".join(_MARKDOWN.sub(" ", text).split())
    folded, positions = _fold(clean)
    at = folded.find(query)
    if at < 0:
        return None
    start = positions[at]
    begin = max(0, start - SNIPPET_CHARS // 3)
    end = min(len(clean), begin + SNIPPET_CHARS)
    if begin > 0 and " " in clean[begin:start]:
        begin = clean.index(" ", begin) + 1  # empezar en una palabra entera
    return ("…" if begin > 0 else "") + clean[begin:end].strip() + ("…" if end < len(clean) else "")


def _search(data: dict[str, Any], query: str) -> tuple[bool, str | None]:
    """¿Contiene la conversación ``query``? Y, si no está en el título, el fragmento donde aparece."""
    if query in _fold(data["title"])[0]:
        return True, None
    for turn in data["turns"]:
        for field in ("message", "reply"):
            value = turn.get(field)
            if isinstance(value, str) and (snippet := _snippet(value, query)):
                return True, snippet
    return False, None


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
        if data is None:
            return None
        # Las respuestas guardadas antes de reparar el doble escape en el protocolo (core/llm.py) se
        # arreglan al leerlas; el archivo no se reescribe.
        turns = [{**t, "reply": undo_double_escape(t["reply"])} if isinstance(t.get("reply"), str) else t for t in data["turns"]]
        return {"id": session_id, **data, "turns": turns, "provider": _last_provider(data)}

    def list(self, query: str | None = None) -> list[dict[str, Any]]:
        """Resumen de cada conversación (sin los turnos), las más recientes primero.

        Con ``query``, solo las que la contienen en el título, en una pregunta o en una respuesta (sin
        distinguir mayúsculas ni tildes); si no está en el título, ``snippet`` dice dónde aparece.
        """
        needle = _fold(" ".join(query.split()))[0] if query else ""
        found = []
        for path in self.directory.glob(f"*{SUFFIX}") if self.directory.is_dir() else []:
            session_id = path.name.removesuffix(SUFFIX)
            if not SESSION_ID.fullmatch(session_id):
                continue
            data = self._read(session_id)
            if data is None:
                continue
            summary = {"id": session_id, "title": data["title"], "updated": data["updated"],
                       "turns": len(data["turns"]), "provider": _last_provider(data)}
            if needle:
                matches, snippet = _search(data, needle)
                if not matches:
                    continue
                summary["snippet"] = snippet
            found.append(summary)
        return sorted(found, key=lambda c: c["updated"], reverse=True)[:MAX_LISTED]

    def rename(self, session_id: str, title: str) -> dict[str, Any] | None:
        """Cambia el título (espacios colapsados); ``None`` si no existe. No cambia ``updated``: renombrar
        no es actividad y la lista no debe reordenarse por ello."""
        clean = " ".join(title.split())
        if not 1 <= len(clean) <= MAX_TITLE_CHARS:
            raise ValueError(f"el título debe tener entre 1 y {MAX_TITLE_CHARS} caracteres")
        data = self._read(session_id)
        if data is None:
            return None
        data["title"] = clean
        write_json_atomic(self._path(session_id), data)
        return {"id": session_id, "title": clean}

    def delete(self, session_id: str) -> bool:
        """Borra la conversación; ``False`` si no existía."""
        path = self._path(session_id)
        existed = path.is_file()
        path.unlink(missing_ok=True)
        return existed


def _last_provider(data: dict[str, Any]) -> str | None:
    """Proveedor del último turno que lo registró (ADR-028); ``None`` en conversaciones anteriores."""
    for turn in reversed(data["turns"]):
        llm = turn.get("llm")
        if isinstance(llm, dict) and isinstance(llm.get("provider"), str):
            return llm["provider"]
    return None
