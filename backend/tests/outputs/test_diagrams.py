"""Tests de validación y guardado de diagramas Mermaid."""

from pathlib import Path

import pytest

from techdoc_agent.outputs.diagrams import save_diagram, validate_mermaid

VALID = {
    "clases": "classDiagram\n    class Queue {\n        +enqueue(nombre) str\n    }\n    Queue <|-- Worker",
    "secuencia": "sequenceDiagram\n    Cliente->>Queue: enqueue(tarea)\n    Queue-->>Cliente: job_id",
    "flujo": "flowchart TD\n    A[Inicio] --> B{¿Cola llena?}\n    B -- Sí --> C[Error]",
    "componentes": "graph LR\n    API --> Queue\n    Queue --> Worker",
    "entidad_relacion": "erDiagram\n    JOB ||--o{ ATTEMPT : tiene\n    JOB {\n        string id\n    }",
    "estados": "stateDiagram-v2\n    [*] --> pending\n    pending --> running\n    running --> done",
}


@pytest.mark.parametrize("tipo", VALID)
def test_valid_diagram_of_each_type(tipo: str) -> None:
    assert validate_mermaid(tipo, "Título", VALID[tipo]) == []


def one_error(tipo: str, code: str, fragment: str, titulo: str = "T") -> None:
    errors = validate_mermaid(tipo, titulo, code)
    assert any(fragment in e for e in errors), errors


def test_empty_code() -> None:
    one_error("flujo", "   \n ", "vacío")


def test_fences_are_rejected() -> None:
    one_error("flujo", "```mermaid\nflowchart TD\nA --> B\n```", "```")


def test_header_must_match_type() -> None:
    one_error("secuencia", "flowchart TD\nA --> B", "sequenceDiagram")
    one_error("flujo", "A --> B", "flowchart")


def test_unclosed_bracket_reports_line_number() -> None:
    one_error("flujo", "flowchart TD\nA[Inicio --> B", "Línea 2: '[' sin cerrar")


def test_unopened_bracket() -> None:
    one_error("flujo", "flowchart TD\nA --> B)", "')' sin su apertura")


def test_brackets_inside_quotes_do_not_count() -> None:
    assert validate_mermaid("flujo", "T", 'flowchart TD\nA["texto ( raro"] --> B') == []


def test_sequence_message_text_is_free() -> None:
    assert validate_mermaid("secuencia", "T", "sequenceDiagram\nA->>B: abre (sin cerrar :)") == []


def test_body_required() -> None:
    one_error("flujo", "flowchart TD", "no tiene contenido")


def test_minimum_element_per_type() -> None:
    one_error("secuencia", "sequenceDiagram\nparticipant A", "mensaje con flecha")
    one_error("flujo", "flowchart TD\nA", "conexión")
    one_error("estados", "stateDiagram-v2\nstate X", "transición")


def test_comments_and_directives_before_header_are_accepted() -> None:
    code = '%%{init: {"theme": "dark"}}%%\n%% un comentario\nflowchart TD\nA --> B'
    assert validate_mermaid("flujo", "T", code) == []


def test_frontmatter_is_skipped() -> None:
    assert validate_mermaid("flujo", "T", "---\ntitle: x\n---\nflowchart TD\nA --> B") == []


def test_invalid_type_and_title() -> None:
    assert "no válido" in validate_mermaid("pastel", "T", "x")[0]
    one_error("flujo", VALID["flujo"], "título", titulo="  ")
    one_error("flujo", VALID["flujo"], "título", titulo="x" * 101)


def test_several_errors_are_reported_together() -> None:
    errors = validate_mermaid("secuencia", " ", "flowchart TD\nA[ --> B")
    assert len(errors) >= 3


def test_too_long_code() -> None:
    one_error("flujo", "flowchart TD\n" + "A --> B\n" * 5000, "supera")


def test_save_uses_generated_name_inside_outputs_dir(tmp_path: Path) -> None:
    name = save_diagram("flujo", "Encolar y procesar", VALID["flujo"], tmp_path / "out")
    assert name.startswith("diagrama-encolar-y-procesar-") and name.endswith(".mmd")
    assert (tmp_path / "out" / name).read_text(encoding="utf-8").startswith("flowchart TD")


def test_malicious_title_cannot_escape_the_directory(tmp_path: Path) -> None:
    out = tmp_path / "out"
    name = save_diagram("flujo", "../../etc/passwd", VALID["flujo"], out)
    assert "/" not in name and ".." not in name
    assert (out / name).exists() and list(tmp_path.glob("*.mmd")) == []


def test_same_title_twice_does_not_collide(tmp_path: Path) -> None:
    names = {save_diagram("flujo", "Igual", VALID["flujo"], tmp_path) for _ in range(5)}
    assert len(names) == 5
