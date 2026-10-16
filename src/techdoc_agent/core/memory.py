"""Historial de conversación por sesión (en memoria, v1)."""

from __future__ import annotations

from techdoc_agent.core.llm import Message


class Memory:
    """Guarda una lista de mensajes por ``session_id``."""

    def __init__(self) -> None:
        self._sessions: dict[str, list[Message]] = {}

    def get(self, session_id: str) -> list[Message]:
        """Devuelve el historial de la sesión (la lista real, se crea si no existe)."""
        return self._sessions.setdefault(session_id, [])

    def clear(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
