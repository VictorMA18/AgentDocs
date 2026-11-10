"""Dataset de evaluación: un caso por línea JSON (formato en docs/07).

``load`` valida el archivo entero y falla con un ``DatasetError`` que indica la línea, para
que un error de formato se vea al instante y no a mitad de una ejecución de varios minutos.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = REPO_ROOT / "evals" / "dataset.jsonl"

KNOWN_TOOLS = ("buscar_documentos", "listar_documentos", "generar_diagrama", "generar_requisitos", "cargar_guia")
ARTIFACTS = ("mermaid", "requisitos")
KINDS = ("exact_term", "distractor", "version", "paraphrase", "attribution")  # tipos de caso difícil de recuperación (Fase 7.A)
_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_LIST_FIELDS = ("expect_tools", "forbid_tools", "expect_sources", "must_include", "must_not_include",
                "must_not_start_with", "setup_docs", "follow_up", "expect_evidence", "expect_cited")
_BOOL_FIELDS = ("out_of_scope", "expect_clarification")


class DatasetError(ValueError):
    """El dataset no cumple el formato."""


@dataclass(frozen=True)
class Case:
    id: str
    question: str
    expect_tools: tuple[str, ...] = ()
    forbid_tools: tuple[str, ...] = ()
    expect_sources: tuple[str, ...] = ()  # fuentes (archivos) que deben aparecer entre los fragmentos recuperados
    expect_evidence: tuple[str, ...] = ()  # textos que deben estar en los fragmentos recuperados (nivel de fragmento)
    expect_cited: tuple[str, ...] = ()  # archivos a los que la respuesta debe atribuir los datos de must_include ([archivo#n])
    must_include: tuple[str, ...] = ()  # en la respuesta final, sin distinguir mayúsculas
    must_not_include: tuple[str, ...] = ()  # no puede aparecer en ninguna parte (p. ej. un literal del prompt)
    must_not_start_with: tuple[str, ...] = ()  # la respuesta no puede empezar así: sería obedecer una orden inyectada
    out_of_scope: bool = False  # la documentación no cubre la pregunta: debe abstenerse
    expect_artifact: str | None = None  # "mermaid" | "requisitos"
    expect_clarification: bool = False  # pregunta ambigua: debe preguntar o declarar su suposición
    max_artifacts: int | None = None  # con expect_artifact: como mucho este nº de archivos de ese tipo en el turno
    max_chars: int | None = None  # la respuesta final no puede superar esta longitud (brevedad)
    setup_docs: tuple[str, ...] = ()  # documentos extra a indexar (rutas desde la raíz del repo)
    follow_up: tuple[str, ...] = ()  # mensajes siguientes en la misma sesión
    kind: str | None = None  # tipo de caso difícil, para reportar la recuperación por tipo
    notes: str = ""


def _parse(raw: dict[str, Any], root: Path) -> Case:
    unknown = set(raw) - {f for f in Case.__dataclass_fields__}
    if unknown:
        raise DatasetError(f"campos desconocidos: {', '.join(sorted(unknown))}")
    for field in ("id", "question"):
        if not isinstance(raw.get(field), str) or not raw[field].strip():
            raise DatasetError(f"'{field}' es obligatorio y debe ser un texto no vacío")
    if not _ID.fullmatch(raw["id"]):
        raise DatasetError(f"id no válido: {raw['id']!r} (minúsculas, números y guiones)")
    for field in _LIST_FIELDS:
        value = raw.get(field, [])
        if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
            raise DatasetError(f"'{field}' debe ser una lista de textos no vacíos")
    for field in _BOOL_FIELDS:
        if not isinstance(raw.get(field, False), bool):
            raise DatasetError(f"'{field}' debe ser true o false")
    if not isinstance(raw.get("notes", ""), str):
        raise DatasetError("'notes' debe ser un texto")
    for field in ("max_artifacts", "max_chars"):
        value = raw.get(field)
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 1):
            raise DatasetError(f"'{field}' debe ser un entero positivo")
    artifact = raw.get("expect_artifact")
    if artifact is not None and artifact not in ARTIFACTS:
        raise DatasetError(f"expect_artifact debe ser uno de {ARTIFACTS}, no {artifact!r}")
    kind = raw.get("kind")
    if kind is not None and kind not in KINDS:
        raise DatasetError(f"kind debe ser uno de {KINDS}, no {kind!r}")
    for tool in raw.get("expect_tools", []) + raw.get("forbid_tools", []):
        if tool not in KNOWN_TOOLS:
            raise DatasetError(f"herramienta desconocida: {tool!r} (conocidas: {', '.join(KNOWN_TOOLS)})")
    for doc in raw.get("setup_docs", []):
        path = (root / doc).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise DatasetError(f"setup_docs: no existe {doc!r} dentro del repositorio")
    values = {k: (tuple(v) if isinstance(v, list) else v) for k, v in raw.items()}
    return Case(**values)


def load(path: str | Path = DEFAULT_DATASET, root: Path = REPO_ROOT) -> list[Case]:
    """Lee y valida un dataset JSONL. Los ids deben ser únicos."""
    path = Path(path)
    if not path.is_file():
        raise DatasetError(f"no existe el dataset: {path}")
    cases: list[Case] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
            if not isinstance(raw, dict):
                raise DatasetError("cada línea debe ser un objeto JSON")
            case = _parse(raw, root)
        except (ValueError, TypeError) as exc:  # DatasetError y JSON inválido
            raise DatasetError(f"{path.name}, línea {number}: {exc}") from None
        if any(c.id == case.id for c in cases):
            raise DatasetError(f"{path.name}, línea {number}: id repetido {case.id!r}")
        cases.append(case)
    if not cases:
        raise DatasetError(f"{path.name} no tiene casos")
    return cases
