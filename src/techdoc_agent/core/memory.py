"""Historial de conversación por sesión (en memoria) con recorte por resumen.

El historial se divide en *turnos*: un mensaje del usuario y todo lo que el
agente hizo hasta responder. Cuando crece demasiado, los turnos antiguos se
sustituyen por un resumen (ver ``summarizer.py``) y se conservan los últimos N.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from techdoc_agent.core.llm import Message

CHARS_PER_TOKEN = 4  # estimación: no hay contador de tokens antes de llamar al LLM


@dataclass
class _Session:
    messages: list[Message] = field(default_factory=list)
    turn_starts: list[int] = field(default_factory=list)  # índice donde empieza cada turno
    summary: str = ""


class Memory:
    """Guarda mensajes, límites de turno y resumen por ``session_id``."""

    def __init__(self) -> None:
        self._sessions: dict[str, _Session] = {}

    def _session(self, session_id: str) -> _Session:
        return self._sessions.setdefault(session_id, _Session())

    def get(self, session_id: str) -> list[Message]:
        """Devuelve el historial de la sesión (la lista real, se crea si no existe)."""
        return self._session(session_id).messages

    def clear(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

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
