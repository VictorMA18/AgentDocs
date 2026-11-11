"""Modelos de entrada de la API (validación con pydantic)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MAX_MESSAGE_CHARS = 8000


class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    session_id: str = Field(pattern=r"^[A-Za-z0-9_-]{8,64}$")
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    # Proveedor de este turno (ADR-028). Sin él: el último de la conversación o LLM_PROVIDER.
    provider: Literal["claude", "gemini"] | None = None
