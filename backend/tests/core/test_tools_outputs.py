"""Tests de las herramientas de salida y de la autocorrección del agente."""

import json
from pathlib import Path

import pytest
from fakes import FakeLLMClient, calls, final

from techdoc_agent.core.agent import Agent
from techdoc_agent.core.memory import Memory
from techdoc_agent.core.tools import ToolRegistry
from techdoc_agent.core.tools_outputs import output_tools

GOOD = "sequenceDiagram\n    Cliente->>Queue: enqueue(tarea)\n    Queue-->>Cliente: job_id"
BAD_HEADER = "flowchart TD\n    A[Inicio --> B"


@pytest.fixture
def registry(tmp_path: Path) -> ToolRegistry:
    return ToolRegistry(output_tools(tmp_path / "out"))


def req(**over: str) -> dict:
    base = {"id": "RF-01", "descripcion": "El sistema debe reintentar", "prioridad": "M",
            "criterio_aceptacion": "Se reintenta max_retries veces", "fuente": "taskflow.md#5"}
    return {**base, **over}


def test_tools_match_doc_schema(registry: ToolRegistry) -> None:
    specs = {s.name: s for s in registry.specs()}
    assert set(specs) == {"generar_diagrama", "generar_requisitos"}
    assert "estados" in specs["generar_diagrama"].input_schema["properties"]["tipo"]["enum"]
    assert specs["generar_requisitos"].input_schema["required"] == ["titulo", "funcionales"]


def test_valid_diagram_is_saved_and_only_the_name_is_returned(registry: ToolRegistry, tmp_path: Path) -> None:
    text, is_error = registry.dispatch(
        "generar_diagrama", {"tipo": "secuencia", "titulo": "Encolar", "codigo": GOOD})
    assert not is_error and "diagrama-encolar-" in text and str(tmp_path) not in text
    assert len(list((tmp_path / "out").glob("*.mmd"))) == 1


def test_invalid_diagram_returns_all_errors_and_saves_nothing(registry: ToolRegistry, tmp_path: Path) -> None:
    text, is_error = registry.dispatch(
        "generar_diagrama", {"tipo": "secuencia", "titulo": "X", "codigo": BAD_HEADER})
    assert is_error and "sequenceDiagram" in text and "vuelve a llamar" in text
    assert not (tmp_path / "out").exists()


def test_missing_argument_is_an_error(registry: ToolRegistry) -> None:
    assert registry.dispatch("generar_diagrama", {"tipo": "flujo"})[1] is True


def test_requirements_saved_with_warnings(registry: ToolRegistry, tmp_path: Path) -> None:
    text, is_error = registry.dispatch(
        "generar_requisitos", {"titulo": "Reintentos", "funcionales": [req(), req(id="RF-02", fuente="")]})
    assert not is_error and "requisitos-reintentos-" in text and "2 funcionales" in text
    assert "Advertencias" in text and "RF-02" in text
    assert len(list((tmp_path / "out").glob("*.md"))) == 1


def test_invalid_requirements_are_rejected_with_reasons(registry: ToolRegistry) -> None:
    text, is_error = registry.dispatch(
        "generar_requisitos", {"titulo": "T", "funcionales": [req(), req(), req(prioridad="Z")]})
    assert is_error and "duplicado" in text and "prioridad" in text


def test_agent_self_corrects_after_validation_error(tmp_path: Path, logs_dir: Path) -> None:
    llm = FakeLLMClient([
        calls(("c1", "generar_diagrama", {"tipo": "secuencia", "titulo": "Encolar", "codigo": BAD_HEADER})),
        calls(("c2", "generar_diagrama", {"tipo": "secuencia", "titulo": "Encolar", "codigo": GOOD})),
        final("Guardado."),
    ])
    agent = Agent(llm, ToolRegistry(output_tools(tmp_path / "out")), Memory())
    result = agent.run("s", "haz un diagrama")
    assert [t.is_error for t in result.tool_calls] == [True, False]
    assert 'error="true"' in llm.seen[1][-1]["content"]  # el modelo vio los errores
    events = [json.loads(line) for f in logs_dir.glob("agent-*.jsonl") for line in f.read_text().splitlines()]
    assert [e["is_error"] for e in events if e["event"] == "tool_call"] == [True, False]
    assert len(list((tmp_path / "out").glob("*.mmd"))) == 1
