"""Conversaciones guardadas: listar, abrir, renombrar y borrar (transcripción, memoria del agente y documentos)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from techdoc_agent.api.deps import Core, get_core
from techdoc_agent.api.schemas import RenameRequest
from techdoc_agent.api.security import valid_conversation_id
from techdoc_agent.core.transcripts import MAX_QUERY_CHARS

router = APIRouter()


@router.get("/api/conversations")
def list_conversations(
    q: str | None = Query(default=None, max_length=MAX_QUERY_CHARS), core: Core = Depends(get_core)
) -> list[dict[str, Any]]:
    """Con ``q``, solo las conversaciones que lo contienen (título, preguntas o respuestas)."""
    return core.transcripts.list(q.strip() or None if q else None)


@router.get("/api/conversations/{conversation_id}")
def get_conversation(conversation_id: str, core: Core = Depends(get_core)) -> dict[str, Any]:
    conversation = core.transcripts.get(valid_conversation_id(conversation_id))
    if conversation is None:
        raise HTTPException(404, "Conversación no encontrada")
    return conversation


@router.patch("/api/conversations/{conversation_id}")
def rename_conversation(conversation_id: str, body: RenameRequest, core: Core = Depends(get_core)) -> dict[str, Any]:
    with core.lock:
        try:
            renamed = core.transcripts.rename(valid_conversation_id(conversation_id), body.title)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
    if renamed is None:
        raise HTTPException(404, "Conversación no encontrada")
    return renamed


@router.delete("/api/conversations/{conversation_id}")
def delete_conversation(conversation_id: str, core: Core = Depends(get_core)) -> dict[str, Any]:
    with core.lock:
        existed = core.transcripts.delete(valid_conversation_id(conversation_id))
        core.agent.memory.clear(conversation_id)  # la memoria del agente, en RAM y en disco
        core.forget(conversation_id)  # sus documentos y su índice (ADR-032)
    if not existed:
        raise HTTPException(404, "Conversación no encontrada")
    return {"id": conversation_id}
