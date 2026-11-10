"""Salud del servicio: responde y cuenta lo indexado."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from techdoc_agent.api.deps import Core, get_core

router = APIRouter()


@router.get("/healthz")
def healthz(core: Core = Depends(get_core)) -> dict[str, Any]:
    return {"status": "ok", "documents": len(core.store.list_sources()), "chunks": core.store.count()}
