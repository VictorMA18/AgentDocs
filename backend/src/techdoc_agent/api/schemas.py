"""Modelos de entrada de la API (validación con pydantic)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

MAX_MESSAGE_CHARS = 8000


class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    session_id: str = Field(pattern=r"^[A-Za-z0-9_-]{8,64}$")
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
