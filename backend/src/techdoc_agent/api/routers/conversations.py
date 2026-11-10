"""Conversaciones guardadas: listar, abrir y borrar (transcripción + memoria del agente)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from techdoc_agent.api.deps import Core, get_core
from techdoc_agent.api.security import valid_conversation_id

router = APIRouter()


@router.get("/api/conversations")
def list_conversations(core: Core = Depends(get_core)) -> list[dict[str, Any]]:
    return core.transcripts.list()


@router.get("/api/conversations/{conversation_id}")
def get_conversation(conversation_id: str, core: Core = Depends(get_core)) -> dict[str, Any]:
    conversation = core.transcripts.get(valid_conversation_id(conversation_id))
    if conversation is None:
        raise HTTPException(404, "Conversación no encontrada")
    return conversation


@router.delete("/api/conversations/{conversation_id}")
def delete_conversation(conversation_id: str, core: Core = Depends(get_core)) -> dict[str, Any]:
    with core.lock:
        existed = core.transcripts.delete(valid_conversation_id(conversation_id))
        core.agent.memory.clear(conversation_id)  # la memoria del agente, en RAM y en disco
    if not existed:
        raise HTTPException(404, "Conversación no encontrada")
    return {"id": conversation_id}
