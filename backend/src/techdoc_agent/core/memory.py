"""Historial de conversación por sesión, con recorte por resumen y persistencia opcional.

El historial se divide en *turnos*: un mensaje del usuario y todo lo que el
agente hizo hasta responder. Cuando crece demasiado, los turnos antiguos se
sustituyen por un resumen (ver ``summarizer.py``) y se conservan los últimos N.

Sin carpeta de almacenamiento todo vive en RAM. Con ella, cada sesión se guarda como
``<session_id>.memory.json`` (ver ``save``) y se vuelve a cargar al pedirla tras un reinicio.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from techdoc_agent.core.llm import Message
from techdoc_agent.core.storage import check_session_id, quarantine, read_json, write_json_atomic

CHARS_PER_TOKEN = 4  # estimación: no hay contador de tokens antes de llamar al LLM
FORMAT_VERSION = 1
ROLES = ("user", "assistant")


@dataclass
class _Session:
    messages: list[Message] = field(default_factory=list)
    turn_starts: list[int] = field(default_factory=list)  # índice donde empieza cada turno
    summary: str = ""


def _session_from_dict(data: Any) -> _Session | None:
    """Reconstruye una sesión guardada; ``None`` si el contenido no tiene la forma esperada."""
    if not isinstance(data, dict) or data.get("version") != FORMAT_VERSION:
        return None
    messages, starts, summary = data.get("messages"), data.get("turn_starts"), data.get("summary")
    if not isinstance(messages, list) or not isinstance(starts, list) or not isinstance(summary, str):
        return None
    if not all(isinstance(m, dict) and m.get("role") in ROLES and isinstance(m.get("content"), str)
               for m in messages):
        return None
    if not all(isinstance(i, int) and 0 <= i <= len(messages) for i in starts) or starts != sorted(starts):
        return None
    return _Session([{"role": m["role"], "content": m["content"]} for m in messages], list(starts), summary)


class Memory:
    """Guarda mensajes, límites de turno y resumen por ``session_id``."""

    def __init__(self, storage_dir: str | Path | None = None) -> None:
        self._sessions: dict[str, _Session] = {}
        self._dir = Path(storage_dir) if storage_dir is not None else None

    def _path(self, session_id: str) -> Path | None:
        if self._dir is None:
            return None
        return self._dir / f"{check_session_id(session_id)}.memory.json"

    def _load(self, session_id: str) -> _Session:
        path = self._path(session_id)
        data = read_json(path) if path else None
        if data is None:
            return _Session()
        session = _session_from_dict(data)
        if session is None:
            quarantine(path, "el contenido no tiene la forma esperada")
            return _Session()
        return session

    def _session(self, session_id: str) -> _Session:
        if session_id not in self._sessions:
            self._sessions[session_id] = self._load(session_id)
        return self._sessions[session_id]

    def save(self, session_id: str) -> None:
        """Guarda la sesión en disco (si hay carpeta). Una sesión vacía no crea archivo."""
        path = self._path(session_id)
        session = self._sessions.get(session_id)
        if path is None or session is None or not (session.messages or session.summary):
            return
        write_json_atomic(path, {
            "version": FORMAT_VERSION, "messages": session.messages,
            "turn_starts": session.turn_starts, "summary": session.summary,
        })

    def get(self, session_id: str) -> list[Message]:
        """Devuelve el historial de la sesión (la lista real, se crea si no existe)."""
        return self._session(session_id).messages

    def clear(self, session_id: str) -> None:
        """Olvida la sesión y borra su archivo."""
        path = self._path(session_id)
        self._sessions.pop(session_id, None)
        if path is not None:
            path.unlink(missing_ok=True)

    # --- turnos ---

    def mark_turn(self, session_id: str) -> None:
        """Marca que el próximo mensaje añadido abre un turno nuevo."""
        s = self._session(session_id)
        s.turn_starts.append(len(s.messages))

    def drop_last_turn(self, session_id: str) -> None:
        """Deshace un turno fallido: quita sus mensajes y su marca."""
        s = self._session(session_id)
        if s.turn_starts:
            del s.messages[s.turn_starts.pop():]

    def turn_count(self, session_id: str) -> int:
        return len(self._session(session_id).turn_starts)

    # --- resumen ---

    def summary(self, session_id: str) -> str:
        return self._session(session_id).summary

    def estimated_tokens(self, session_id: str) -> int:
        s = self._session(session_id)
        chars = len(s.summary) + sum(len(m["content"]) for m in s.messages)
        return chars // CHARS_PER_TOKEN

    def old_messages(self, session_id: str, keep_turns: int) -> list[Message]:
        """Mensajes de los turnos que se resumirían (todos salvo los últimos ``keep_turns``)."""
        s = self._session(session_id)
        if len(s.turn_starts) <= keep_turns:
            return []
        return list(s.messages[: s.turn_starts[-keep_turns]]) if keep_turns else list(s.messages)

    def compact(self, session_id: str, summary: str, keep_turns: int) -> None:
        """Sustituye los turnos antiguos por ``summary``; conserva los últimos ``keep_turns``."""
        s = self._session(session_id)
        if len(s.turn_starts) <= keep_turns:
            return
        cut = s.turn_starts[-keep_turns] if keep_turns else len(s.messages)
        del s.messages[:cut]
        s.turn_starts = [i - cut for i in s.turn_starts[len(s.turn_starts) - keep_turns:]] if keep_turns else []
        s.summary = summary
