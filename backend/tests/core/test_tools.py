"""Tests del registro y despacho de herramientas."""

import pytest
from fakes import toy_tools

from techdoc_agent.core.tools import (
    Tool,
    ToolRegistry,
    ToolResult,
    format_tool_results,
)


@pytest.fixture
def registry() -> ToolRegistry:
    return ToolRegistry(toy_tools())


def test_dispatch_ok(registry: ToolRegistry) -> None:
    assert registry.dispatch("sumar", {"a": 17, "b": 25}) == ("42", False)


def test_dispatch_tool_without_args(registry: ToolRegistry) -> None:
    text, is_error = registry.dispatch("obtener_hora", {})
    assert not is_error and "T" in text  # ISO 8601


def test_unknown_tool_is_error_and_lists_available(registry: ToolRegistry) -> None:
    text, is_error = registry.dispatch("no_existe", {})
    assert is_error
    assert "no_existe" in text and "sumar" in text


def test_invalid_args_is_error_not_exception(registry: ToolRegistry) -> None:
    text, is_error = registry.dispatch("sumar", {"a": 1, "c": 2})
    assert is_error and "TypeError" in text


def test_non_object_args_is_error(registry: ToolRegistry) -> None:
    assert registry.dispatch("sumar", [1, 2])[1] is True


def test_sumar_edge_cases_fail_on_purpose(registry: ToolRegistry) -> None:
    text, is_error = registry.dispatch("sumar", {"a": 10**13, "b": 1})
    assert is_error and "fuera de rango" in text
    text, is_error = registry.dispatch("sumar", {"a": "3", "b": 1})
    assert is_error and "ValueError" in text


def test_exception_in_tool_is_captured() -> None:
    def boom() -> str:
        raise RuntimeError("fallo interno")

    registry = ToolRegistry([Tool("boom", "falla", {"type": "object"}, boom)])
    assert registry.dispatch("boom", {}) == ("Error en boom: RuntimeError: fallo interno", True)


def test_duplicate_registration_rejected(registry: ToolRegistry) -> None:
    with pytest.raises(ValueError, match="duplicada"):
        registry.register(toy_tools()[0])


def test_specs_expose_name_description_and_schema(registry: ToolRegistry) -> None:
    specs = {s.name: s for s in registry.specs()}
    assert set(specs) == {"obtener_hora", "sumar"}
    assert specs["sumar"].input_schema["required"] == ["a", "b"]


def test_format_tool_results_one_block_per_call() -> None:
    out = format_tool_results(
        [ToolResult("c1", "14:32", False), ToolResult("c2", "boom", True)]
    )
    assert out.splitlines() == [
        '<resultado_herramienta id="c1" error="false">14:32</resultado_herramienta>',
        '<resultado_herramienta id="c2" error="true">boom</resultado_herramienta>',
    ]
