"""Proveedores del LLM que se pueden elegir en la interfaz (ADR-028). Nunca expone la clave."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from techdoc_agent.api.deps import Core, get_core

router = APIRouter()


@router.get("/api/providers")
def list_providers(core: Core = Depends(get_core)) -> list[dict[str, Any]]:
    return core.provider_status()
