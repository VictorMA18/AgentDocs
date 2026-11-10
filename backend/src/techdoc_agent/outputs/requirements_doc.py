"""Validación, render a Markdown y guardado de documentos de requisitos.

El modelo redacta los requisitos; aquí se comprueba su estructura (ids únicos,
prioridad MoSCoW, criterio de aceptación o métrica) y se devuelven errores claros
para que se corrija. No genera contenido.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

from techdoc_agent.outputs.naming import write_unique

RF_ID = re.compile(r"^RF-\d{2,3}$")
RNF_ID = re.compile(r"^RNF-\d{2,3}$")
PRIORITIES = {"M": "Must", "S": "Should", "C": "Could", "W": "Won't"}
MAX_TITLE_CHARS = 100
MAX_ERRORS = 10


def _text(item: dict[str, Any], key: str) -> str:
    value = item.get(key, "")
    return value.strip() if isinstance(value, str) else ""


def _check_list(
    items: Any, label: str, id_pattern: re.Pattern[str], required: tuple[str, ...], seen: set[str],
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(items, list):
        return [f"{label} debe ser una lista."], warnings
    for position, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            errors.append(f"{label} #{position}: debe ser un objeto.")
            continue
        rid = _text(item, "id")
        name = rid or f"{label} #{position}"
        if not id_pattern.match(rid):
            errors.append(f"{name}: id inválido (formato {id_pattern.pattern}).")
        elif rid in seen:
            errors.append(f"{rid}: id duplicado.")
        seen.add(rid)
        for key in required:
            if not _text(item, key):
                errors.append(f"{name}: falta '{key}' o está vacío.")
        if "prioridad" in required and _text(item, "prioridad") not in PRIORITIES:
            errors.append(f"{name}: prioridad debe ser M, S, C o W.")
        if "fuente" in item or label == "funcionales":
            if not _text(item, "fuente"):
                warnings.append(f"{name}: sin 'fuente' (documento y fragmento de donde se deduce).")
    return errors, warnings


def validate_requirements(
    titulo: Any, funcionales: Any, no_funcionales: Any = None
) -> tuple[list[str], list[str]]:
    """Devuelve ``(errores, avisos)``. Con errores el documento no se guarda."""
    errors: list[str] = []
    if not isinstance(titulo, str) or not titulo.strip():
        errors.append("El título no puede estar vacío.")
    elif len(titulo) > MAX_TITLE_CHARS:
        errors.append(f"El título supera {MAX_TITLE_CHARS} caracteres.")
    if not funcionales:
        errors.append("Debe haber al menos un requisito funcional.")
    seen: set[str] = set()
    e1, w1 = _check_list(
        funcionales or [], "funcionales", RF_ID,
        ("descripcion", "prioridad", "criterio_aceptacion"), seen,
    )
    e2, w2 = _check_list(
        no_funcionales or [], "no_funcionales", RNF_ID,
        ("categoria", "descripcion", "metrica"), seen,
    )
    return (errors + e1 + e2)[:MAX_ERRORS], w1 + w2


def _cell(value: Any) -> str:
    """Texto seguro para una celda de tabla Markdown."""
    return str(value or "").strip().replace("|", "\\|").replace("\n", " ")


def render_requirements(titulo: str, funcionales: list[dict], no_funcionales: list[dict]) -> str:
    lines = [f"# {titulo.strip()}", "", f"_Generado el {date.today().isoformat()}_", "",
             "## Requisitos funcionales", "",
             "| ID | Descripción | Prioridad | Criterio de aceptación | Fuente |",
             "|---|---|---|---|---|"]
    for r in funcionales:
        lines.append(
            f"| {_cell(r['id'])} | {_cell(r['descripcion'])} | {_cell(r['prioridad'])} "
            f"({PRIORITIES[r['prioridad'].strip()]}) | {_cell(r['criterio_aceptacion'])} "
            f"| {_cell(r.get('fuente'))} |"
        )
    if no_funcionales:
        lines += ["", "## Requisitos no funcionales", "",
                  "| ID | Categoría | Descripción | Métrica |", "|---|---|---|---|"]
        for r in no_funcionales:
            lines.append(
                f"| {_cell(r['id'])} | {_cell(r['categoria'])} | {_cell(r['descripcion'])} "
                f"| {_cell(r['metrica'])} |"
            )
    return "\n".join(lines) + "\n"


def save_requirements(
    titulo: str, funcionales: list[dict], no_funcionales: list[dict] | None, outputs_dir: Path
) -> str:
    """Guarda el documento ya validado como ``requisitos-<slug>-<id>.md``; devuelve el nombre."""
    content = render_requirements(titulo, funcionales, no_funcionales or [])
    return write_unique(outputs_dir, "requisitos", titulo, "md", content)
