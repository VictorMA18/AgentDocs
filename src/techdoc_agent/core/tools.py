"""Registro y despacho de herramientas del agente.

Una herramienta tiene nombre, descripción (lo que el modelo lee para decidir),
``input_schema`` (JSON Schema de sus argumentos) y una función Python.
``ToolRegistry.dispatch`` nunca lanza excepciones: devuelve ``(texto, is_error)``
para que un fallo llegue al modelo como información y no rompa el bucle.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

# Rango aceptado por ``sumar``: caso borde que falla a propósito (solo Fase 1).
_MAX_ABS = 1e12


@dataclass(frozen=True)
class ToolSpec:
    """Lo que el modelo ve de una herramienta."""

    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    func: Callable[..., Any]


@dataclass(frozen=True)
class ToolResult:
    """Resultado de ejecutar una llamada, listo para devolverse al modelo."""

    call_id: str
    content: str
    is_error: bool


class ToolRegistry:
    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Herramienta duplicada: {tool.name}")
        self._tools[tool.name] = tool

    def specs(self) -> list[ToolSpec]:
        return [ToolSpec(t.name, t.description, t.input_schema) for t in self._tools.values()]

    def dispatch(self, name: str, args: Any) -> tuple[str, bool]:
        """Ejecuta una herramienta. Devuelve ``(texto, is_error)``; nunca lanza."""
        tool = self._tools.get(name)
        if tool is None:
            disponibles = ", ".join(self._tools) or "ninguna"
            return f"Herramienta desconocida: {name!r}. Disponibles: {disponibles}.", True
        if not isinstance(args, dict):
            return f"Los argumentos de {name} deben ser un objeto JSON.", True
        try:
            return str(tool.func(**args)), False
        except Exception as exc:  # noqa: BLE001 - el modelo debe poder ver cualquier fallo
            return f"Error en {name}: {type(exc).__name__}: {exc}", True


def format_tool_results(results: list[ToolResult]) -> str:
    """Un bloque ``<resultado_herramienta>`` por llamada, en un único mensaje."""
    return "\n".join(
        f'<resultado_herramienta id="{r.call_id}" error="{str(r.is_error).lower()}">'
        f"{r.content}</resultado_herramienta>"
        for r in results
    )


# --- Herramientas de juguete (Fase 1; se retiran en la Fase 3) ---


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
