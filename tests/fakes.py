"""Dobles de prueba compartidos."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from techdoc_agent.core.llm import LLMReply, Message, ToolCall
from techdoc_agent.core.tools import Tool, ToolSpec
from techdoc_agent.rag.embeddings import normalize


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
    systems: list[str] = field(default_factory=list)  # system prompt en cada llamada

    def complete(self, system: str, messages: list[Message], tools: list[ToolSpec]) -> LLMReply:
        self.systems.append(system)
        self.seen.append([dict(m) for m in messages])  # copia: el historial sigue mutando
        if not self.script:
            raise AssertionError("El guion del LLM falso se agotó")
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


class HashingEmbedder:
    """Embedder determinista sin modelo: bolsa de palabras con hash a ``dimension`` columnas.

    Textos que comparten palabras tienen vectores parecidos; basta para probar
    el almacén y la ingesta sin descargar nada.
    """

    def __init__(self, dimension: int = 64) -> None:
        self.dimension = dimension

    def _vector(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dimension, dtype=np.float32)
        for word in re.findall(r"\w+", text.lower()):
            digest = hashlib.md5(word.encode()).digest()  # noqa: S324 - no es criptografía
            vec[int.from_bytes(digest[:4], "little") % self.dimension] += 1.0
        return vec

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dimension), dtype=np.float32)
        return normalize(np.stack([self._vector(t) for t in texts]))

    def embed_query(self, text: str) -> np.ndarray:
        return self.embed_documents([text])[0]


# --- Herramientas de juguete (Fase 1): solo para probar el bucle del agente ---

# Rango aceptado por ``sumar``: caso borde que falla a propósito.
_MAX_ABS = 1e12


def obtener_hora() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sumar(a: float, b: float) -> float:
    """Suma dos números. Rechaza no numéricos y valores fuera de rango."""
    for valor in (a, b):
        if isinstance(valor, bool) or not isinstance(valor, int | float):
            raise ValueError(f"se esperaba un número, se recibió {valor!r}")
        if abs(valor) > _MAX_ABS:
            raise ValueError(f"{valor} fuera de rango (máximo {_MAX_ABS:g})")
    return a + b


def toy_tools() -> list[Tool]:
    numero = {"type": "number"}
    return [
        Tool(
            name="obtener_hora",
            description="Devuelve la fecha y hora local actual en formato ISO 8601.",
            input_schema={"type": "object", "properties": {}},
            func=obtener_hora,
        ),
        Tool(
            name="sumar",
            description="Suma dos números. Los valores deben estar entre -1e12 y 1e12.",
            input_schema={
                "type": "object",
                "properties": {"a": numero, "b": numero},
                "required": ["a", "b"],
            },
            func=sumar,
        ),
    ]
