"""Dobles de prueba compartidos."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from techdoc_agent.core.llm import LLMReply, Message, ToolCall
from techdoc_agent.core.tools import ToolSpec


def final(text: str, input_tokens: int = 10, output_tokens: int = 5) -> LLMReply:
    """Respuesta final del modelo."""
    raw = json.dumps({"accion": "responder", "texto": text}, ensure_ascii=False)
    return LLMReply(text=text, input_tokens=input_tokens, output_tokens=output_tokens, raw=raw)


def calls(*tool_calls: tuple[str, str, dict[str, Any]], input_tokens: int = 10) -> LLMReply:
    """El modelo pide herramientas: cada tupla es ``(id, nombre, args)``."""
    parsed = [ToolCall(i, n, a) for i, n, a in tool_calls]
    raw = json.dumps(
        {"accion": "herramientas",
         "llamadas": [{"id": i, "nombre": n, "args": a} for i, n, a in tool_calls]},
        ensure_ascii=False,
    )
    return LLMReply(text=None, tool_calls=parsed, input_tokens=input_tokens, output_tokens=5, raw=raw)


@dataclass
class FakeLLMClient:
    """LLM con guion: devuelve (o lanza) lo que se le indique, en orden."""

    script: list[LLMReply | Exception]
    seen: list[list[Message]] = field(default_factory=list)  # historial en cada llamada

    def complete(self, system: str, messages: list[Message], tools: list[ToolSpec]) -> LLMReply:
        self.seen.append([dict(m) for m in messages])  # copia: el historial sigue mutando
        if not self.script:
            raise AssertionError("El guion del LLM falso se agotó")
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step
