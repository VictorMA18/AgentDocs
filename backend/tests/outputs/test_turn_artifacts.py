"""Detección de los archivos que guardó cada herramienta de salida en un turno."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from techdoc_agent.outputs.artifacts import turn_artifacts


@dataclass
class Trace:
    name: str
    result: str
    args: dict[str, Any] = field(default_factory=dict)
    is_error: bool = False


def test_diagram_and_requirements_are_reported_with_type_and_title(tmp_path: Path) -> None:
    (tmp_path / "diagrama-flujo-cola-3f2a.mmd").write_text("flowchart TD\n A --> B", encoding="utf-8")
    (tmp_path / "requisitos-reintentos-9c1d.md").write_text("# Requisitos", encoding="utf-8")
    traces = [
        Trace("buscar_documentos", "<documento …>"),
        Trace("generar_diagrama", "Diagrama válido y guardado como diagrama-flujo-cola-3f2a.mmd.", {"titulo": "Cola"}),
        Trace("generar_requisitos", "Requisitos guardados como requisitos-reintentos-9c1d.md (5 funcionales).",
              {"titulo": "Reintentos"}),
    ]
    assert turn_artifacts(traces, tmp_path) == [
        {"name": "diagrama-flujo-cola-3f2a.mmd", "type": "mermaid", "title": "Cola"},
        {"name": "requisitos-reintentos-9c1d.md", "type": "requirements", "title": "Reintentos"},
    ]


def test_failed_or_unrelated_calls_are_ignored(tmp_path: Path) -> None:
    (tmp_path / "diagrama-x-1111.mmd").write_text("x", encoding="utf-8")
    traces = [
        Trace("generar_diagrama", "Error: corrige", is_error=True),
        Trace("generar_diagrama", "Diagrama válido y guardado como diagrama-x-1111.mmd.", is_error=True),
        Trace("buscar_documentos", "guardado como diagrama-x-1111.mmd"),  # no es una herramienta de salida
    ]
    assert turn_artifacts(traces, tmp_path) == []


def test_name_that_does_not_exist_on_disk_is_ignored(tmp_path: Path) -> None:
    trace = Trace("generar_diagrama", "Diagrama válido y guardado como diagrama-fantasma-0000.mmd.")
    assert turn_artifacts([trace], tmp_path) == []


def test_missing_title_is_empty_and_unknown_extensions_are_ignored(tmp_path: Path) -> None:
    (tmp_path / "diagrama-a-2222.mmd").write_text("x", encoding="utf-8")
    (tmp_path / "otro.txt").write_text("x", encoding="utf-8")
    traces = [Trace("generar_diagrama", "guardado como diagrama-a-2222.mmd."),
              Trace("generar_diagrama", "guardado como otro.txt")]
    assert turn_artifacts(traces, tmp_path) == [{"name": "diagrama-a-2222.mmd", "type": "mermaid", "title": ""}]
