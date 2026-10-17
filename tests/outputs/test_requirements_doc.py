"""Tests de validación, render y guardado de requisitos."""

from pathlib import Path

from techdoc_agent.outputs.requirements_doc import (
    render_requirements,
    save_requirements,
    validate_requirements,
)


def rf(i: int = 1, **over: str) -> dict:
    base = {"id": f"RF-{i:02d}", "descripcion": "El sistema debe reintentar tareas fallidas",
            "prioridad": "M", "criterio_aceptacion": "Tras fallar, se reintenta hasta max_retries",
            "fuente": "taskflow.md#5"}
    return {**base, **over}


def rnf(i: int = 1, **over: str) -> dict:
    base = {"id": f"RNF-{i:02d}", "categoria": "Fiabilidad",
            "descripcion": "La espera entre reintentos es exponencial", "metrica": "backoff_base ** intento s"}
    return {**base, **over}


def errors(titulo="T", funcionales=None, no_funcionales=None) -> list[str]:
    return validate_requirements(titulo, [rf()] if funcionales is None else funcionales, no_funcionales)[0]


def test_valid_document_has_no_errors_or_warnings() -> None:
    assert validate_requirements("Reintentos", [rf(1), rf(2)], [rnf(1)]) == ([], [])


def test_title_and_empty_functional_list() -> None:
    assert any("título" in e for e in errors(titulo=" "))
    assert any("al menos un requisito" in e for e in errors(funcionales=[]))


def test_invalid_and_duplicate_ids() -> None:
    assert any("id inválido" in e for e in errors(funcionales=[rf(id="REQ-1")]))
    assert any("RF-01: id duplicado" in e for e in errors(funcionales=[rf(1), rf(1)]))
    assert any("id inválido" in e for e in errors(no_funcionales=[rnf(id="RF-01")]))


def test_duplicate_non_functional_ids() -> None:
    assert errors(no_funcionales=[rnf(1), rnf(1)]) and any(
        "duplicado" in e for e in errors(no_funcionales=[rnf(1), rnf(1)]))


def test_priority_and_required_fields() -> None:
    assert any("prioridad" in e for e in errors(funcionales=[rf(prioridad="X")]))
    assert any("criterio_aceptacion" in e for e in errors(funcionales=[rf(criterio_aceptacion=" ")]))
    assert any("descripcion" in e for e in errors(funcionales=[rf(descripcion="")]))
    assert any("metrica" in e for e in errors(no_funcionales=[rnf(metrica="")]))


def test_wrong_types_are_errors_not_exceptions() -> None:
    assert errors(funcionales="no es lista")
    assert errors(funcionales=["texto"])
    assert errors(funcionales=[rf(id=5)])  # id numérico


def test_missing_source_is_only_a_warning() -> None:
    errs, warns = validate_requirements("T", [rf(fuente="")], None)
    assert errs == [] and any("sin 'fuente'" in w for w in warns)


def test_all_problems_reported_together() -> None:
    assert len(errors(titulo="", funcionales=[rf(id="X"), rf(prioridad="Z")])) >= 3


def test_render_escapes_pipes_and_newlines() -> None:
    md = render_requirements("Doc", [rf(descripcion="a | b\nc")], [rnf()])
    assert "a \\| b c" in md and "## Requisitos no funcionales" in md
    assert "| RF-01 |" in md and "M (Must)" in md


def test_render_without_non_functional_section() -> None:
    assert "no funcionales" not in render_requirements("Doc", [rf()], [])


def test_save_generates_name_and_file(tmp_path: Path) -> None:
    name = save_requirements("Reintentos de TaskFlow", [rf()], [rnf()], tmp_path / "out")
    assert name.startswith("requisitos-reintentos-de-taskflow-") and name.endswith(".md")
    assert "RNF-01" in (tmp_path / "out" / name).read_text(encoding="utf-8")
